"""
Fetch YouTube transcript and summarize with Claude Haiku.
Called for each YouTube article during the fetch pipeline.

Transcript sources (in priority order):
1. youtube-transcript-api — fast, no cookies needed, handles auto-captions
2. yt-dlp subtitle download — fallback if transcript API fails
"""
import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Limit concurrent Anthropic API calls to avoid rate limits
_ANTHROPIC_SEMAPHORE = asyncio.Semaphore(3)

def _api_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "")

_COOKIES_PATH = Path(__file__).parent.parent / "youtube_cookies.txt"

def _cookies_file() -> str | None:
    return str(_COOKIES_PATH) if _COOKIES_PATH.exists() else None

# Max transcript chars sent to Claude
_TRANSCRIPT_CHAR_LIMIT = 8_000


# ---------------------------------------------------------------------------
# Transcript fetching
# ---------------------------------------------------------------------------

def _get_transcript_api(video_id: str) -> str:
    """Fetch transcript via youtube-transcript-api (fast, no cookies needed)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        logger.debug("youtube-transcript-api not installed, skipping")
        return ""

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Prefer manual English captions, then auto-generated
        transcript = None
        try:
            transcript = transcript_list.find_manually_created_transcript(["en", "en-US", "en-GB"])
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(["en", "en-US", "en-GB"])
            except Exception:
                pass

        if not transcript:
            return ""

        entries = transcript.fetch()
        text = " ".join(entry.get("text", "") for entry in entries if entry.get("text"))
        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    except Exception as e:
        logger.debug("Transcript API failed for %s: %s", video_id, e)
        return ""


def _parse_vtt(vtt: str) -> str:
    """Extract plain text from a WebVTT subtitle file, deduplicating rolling captions."""
    seen: set[str] = set()
    lines: list[str] = []
    for line in vtt.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("Kind:") \
                or line.startswith("Language:") or "-->" in line \
                or re.match(r"^\d+$", line):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    text = " ".join(lines)
    return re.sub(r" {2,}", " ", text).strip()


def _get_transcript_ytdlp(video_id: str) -> str:
    """Fallback: fetch captions via yt-dlp."""
    try:
        import yt_dlp
    except ImportError:
        return ""

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "en-US", "en-GB"],
            "subtitlesformat": "vtt",
            "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
            "ignoreerrors": True,
            "ignore_no_formats_error": True,
        }
        cookies = _cookies_file()
        if cookies:
            ydl_opts["cookiefile"] = cookies

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        except Exception as e:
            logger.debug("yt-dlp subtitle download error for %s: %s", video_id, e)

        for fname in os.listdir(tmpdir):
            if fname.endswith(".vtt"):
                try:
                    vtt = Path(tmpdir, fname).read_text(encoding="utf-8", errors="ignore")
                    return _parse_vtt(vtt)
                except Exception:
                    return ""

    return ""


def _get_transcript_sync(video_id: str) -> str:
    """Fetch transcript — tries youtube-transcript-api first, then yt-dlp fallback."""
    # Primary: youtube-transcript-api (fast, reliable, no cookies)
    text = _get_transcript_api(video_id)
    if text:
        return text

    # Fallback: yt-dlp subtitle download
    text = _get_transcript_ytdlp(video_id)
    if text:
        return text

    logger.debug("No transcript found for %s", video_id)
    return ""


async def get_transcript(video_id: str) -> str:
    """Async wrapper around the sync transcript fetch."""
    return await asyncio.to_thread(_get_transcript_sync, video_id)


# ---------------------------------------------------------------------------
# Summarization
# ---------------------------------------------------------------------------

async def summarize_transcript(title: str, transcript: str) -> str:
    """
    Use Claude Haiku to produce a smart summary.
    Falls back to a raw transcript excerpt if the API key is missing.
    """
    if not transcript:
        return ""

    api_key = _api_key()
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — using transcript excerpt as summary")
        excerpt = transcript[:600].rstrip()
        return excerpt + ("…" if len(transcript) > 600 else "")

    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed. Run: pip install anthropic")
        return transcript[:300]

    truncated = transcript[:_TRANSCRIPT_CHAR_LIMIT]

    prompt = (
        f'Video title: "{title}"\n\n'
        f"Transcript excerpt:\n{truncated}\n\n"
        "Write a smart 3-paragraph summary of this video for an AI news digest. "
        "Paragraph 1: What the video is about and its main thesis. "
        "Paragraph 2: The key insights, findings, or arguments made. "
        "Paragraph 3: Takeaways, implications, or conclusions for the AI field. "
        "Write in third person. Do not start with 'This video'. "
        "Each paragraph should be 2-3 sentences. Separate paragraphs with a blank line."
    )

    def _call_api() -> tuple[str, int, int]:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip(), msg.usage.input_tokens, msg.usage.output_tokens

    try:
        async with _ANTHROPIC_SEMAPHORE:
            summary, input_tok, output_tok = await asyncio.to_thread(_call_api)
        from app.database import log_api_usage
        log_api_usage("claude-haiku-4-5-20251001", input_tok, output_tok, "youtube_summary")
        logger.debug("Summarized '%s': %d chars", title[:50], len(summary))
        return summary
    except Exception as e:
        logger.error("Summarization API failed for '%s': %s", title[:50], e)
        return transcript[:300]


async def fetch_transcript_and_summarize(video_id: str, title: str) -> str:
    """
    High-level helper: fetch transcript -> summarize -> return summary string.
    Returns '' if the video has no captions.
    """
    transcript = await get_transcript(video_id)
    if not transcript:
        logger.debug("No transcript available for %s", video_id)
        return ""
    logger.info("Transcript fetched for '%s' (%d chars) — summarizing…", title[:50], len(transcript))
    return await summarize_transcript(title, transcript)
