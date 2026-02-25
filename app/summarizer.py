"""
Fetch YouTube transcript via youtube-transcript-api and summarize with Claude Haiku.
Called for each YouTube article during the fetch pipeline.
"""
import asyncio
import logging
import os
import time
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


def _get_transcript_sync(video_id: str) -> str:
    """Fetch auto-generated captions via youtube-transcript-api. Returns plain text or ''."""
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
    )

    cookies_path = _cookies_file()
    if cookies_path:
        import requests
        from http.cookiejar import MozillaCookieJar
        session = requests.Session()
        jar = MozillaCookieJar(cookies_path)
        jar.load(ignore_discard=True, ignore_expires=True)
        session.cookies = jar
        api = YouTubeTranscriptApi(http_client=session)
        logger.debug("Using cookies file for transcript fetch")
    else:
        api = YouTubeTranscriptApi()

    try:
        # Try English first; fall back to any available language
        try:
            transcript = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        except NoTranscriptFound:
            listing = api.list(video_id)
            # Take first available transcript (auto-generated preferred)
            for t in listing:
                if t.is_generated:
                    transcript = t.fetch()
                    break
            else:
                for t in listing:
                    transcript = t.fetch()
                    break
                else:
                    return ""

        snippets = list(transcript)
        text = " ".join(s.text for s in snippets)
        # Clean up common artifacts
        text = text.replace("\n", " ").replace("[Music]", "").replace("[Applause]", "")
        # Collapse extra spaces
        import re
        text = re.sub(r" {2,}", " ", text).strip()
        return text

    except (TranscriptsDisabled, VideoUnavailable) as e:
        logger.debug("No transcript for %s: %s", video_id, e)
        return ""
    except Exception as e:
        # Re-raise IP/request blocks so callers can retry
        if type(e).__name__ in ("IpBlocked", "RequestBlocked"):
            raise
        logger.debug("Transcript fetch failed for %s: %s", video_id, e)
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
