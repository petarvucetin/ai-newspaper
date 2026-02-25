"""
Fetch YouTube transcript via yt-dlp and summarize with Claude Haiku.
Called for each YouTube article during the fetch pipeline.
"""
import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # pick up .env whenever it exists, even if added after process start

logger = logging.getLogger(__name__)

# Read lazily so adding .env and restarting the server picks it up
def _api_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "")

# Optional cookies file to bypass YouTube IP blocks
_COOKIES_PATH = Path(__file__).parent.parent / "youtube_cookies.txt"

def _cookies_file() -> str | None:
    return str(_COOKIES_PATH) if _COOKIES_PATH.exists() else None

# Max transcript chars sent to Claude (keeps token cost low — ~2k tokens)
_TRANSCRIPT_CHAR_LIMIT = 8_000


def _parse_vtt(vtt: str) -> str:
    """Extract plain text from a WebVTT subtitle file, deduplicating rolling captions."""
    seen: set[str] = set()
    lines: list[str] = []
    for line in vtt.splitlines():
        line = line.strip()
        # Skip header, timing cues, and empty lines
        if not line or line.startswith("WEBVTT") or line.startswith("Kind:") \
                or line.startswith("Language:") or "-->" in line \
                or re.match(r"^\d+$", line):
            continue
        # Strip VTT inline tags: <00:00:01.234>, <c>, </c>, <b>, etc.
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    text = " ".join(lines)
    return re.sub(r" {2,}", " ", text).strip()


def _get_transcript_sync(video_id: str) -> str:
    """Fetch auto-generated captions via yt-dlp. Returns plain text or ''."""
    import yt_dlp

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
        }
        cookies = _cookies_file()
        if cookies:
            ydl_opts["cookiefile"] = cookies
            logger.debug("Using cookies file for transcript fetch")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        except Exception as e:
            logger.debug("yt-dlp download error for %s: %s", video_id, e)
            return ""

        # Find any .vtt file written to tmpdir
        for fname in os.listdir(tmpdir):
            if fname.endswith(".vtt"):
                try:
                    vtt = Path(tmpdir, fname).read_text(encoding="utf-8", errors="ignore")
                    return _parse_vtt(vtt)
                except Exception as e:
                    logger.debug("VTT parse error for %s: %s", video_id, e)
                    return ""

    logger.debug("No subtitles found for %s", video_id)
    return ""


async def get_transcript(video_id: str) -> str:
    """Async wrapper around the sync transcript fetch."""
    return await asyncio.to_thread(_get_transcript_sync, video_id)


async def summarize_transcript(title: str, transcript: str) -> str:
    """
    Use Claude Haiku to produce a 2-3 sentence smart summary.
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

    def _call_api() -> str:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    try:
        summary = await asyncio.to_thread(_call_api)
        logger.debug("Summarized '%s': %d chars", title[:50], len(summary))
        return summary
    except Exception as e:
        logger.error("Summarization API failed for '%s': %s", title[:50], e)
        return transcript[:300]


async def fetch_transcript_and_summarize(video_id: str, title: str) -> str:
    """
    High-level helper: fetch transcript → summarize → return summary string.
    Returns '' if the video has no captions.
    """
    transcript = await get_transcript(video_id)
    if not transcript:
        logger.debug("No transcript available for %s", video_id)
        return ""
    logger.info("Transcript fetched for '%s' (%d chars) — summarizing…", title[:50], len(transcript))
    return await summarize_transcript(title, transcript)
