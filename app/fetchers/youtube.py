import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from app.fetchers.base import RawArticle
from app import config

logger = logging.getLogger(__name__)

_COOKIES_PATH = Path(__file__).parent.parent.parent / "youtube_cookies.txt"

def _cookies_file() -> str | None:
    return str(_COOKIES_PATH) if _COOKIES_PATH.exists() else None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_CHANNEL_DELAY = 5        # seconds between channel fetches
_MAX_429_RETRIES = 3      # retry attempts on HTTP 429


def _parse_upload_date(upload_date: str | None) -> datetime:
    if upload_date:
        try:
            return datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _build_article(entry: dict, source_name: str) -> RawArticle | None:
    vid_id = entry.get("id", "")
    title = (entry.get("title") or "").strip()
    if not vid_id or not title:
        return None
    return RawArticle(
        source_name=source_name,
        external_id=vid_id,
        title=title,
        url=f"https://www.youtube.com/watch?v={vid_id}",
        author=entry.get("uploader") or entry.get("channel") or "",
        published_at=_parse_upload_date(entry.get("upload_date")),
        thumbnail_url="",  # thumbnails disabled
        upvotes=entry.get("view_count") or 0,
        summary="",  # filled in later by summarizer
    )


def validate_channel_handle(handle: str) -> bool:
    """Check if a YouTube channel handle exists via a lightweight HEAD request."""
    import httpx
    handle = handle.lstrip("@")
    url = f"https://www.youtube.com/@{handle}"
    try:
        resp = httpx.head(url, follow_redirects=True, timeout=10,
                          headers={"User-Agent": "Mozilla/5.0"})
        return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fetch pinned channels
# ---------------------------------------------------------------------------

def _fetch_channels_sync(channels: list[str], limit: int, cutoff: datetime) -> list[RawArticle]:
    """Fetch latest videos from each channel via yt-dlp with rate limiting."""
    import time
    import yt_dlp
    from app.fetch_state import state as fetch_state

    cookies = _cookies_file()
    results: list[RawArticle] = []
    succeeded = 0
    failures: list[str] = []

    for idx, handle in enumerate(channels):
        handle = handle.lstrip("@")
        source_name = f"@{handle}"
        url = f"https://www.youtube.com/@{handle}/videos"

        # Rate limit: delay between channels
        if idx > 0:
            time.sleep(_CHANNEL_DELAY)

        logger.info("YouTube channels: fetching @%s (%d/%d)", handle, idx + 1, len(channels))
        fetch_state.add(f"YouTube: fetching @{handle} ({idx + 1}/{len(channels)})")

        # Validate handle before trying yt-dlp
        if not validate_channel_handle(handle):
            failures.append(f"@{handle}: handle not found")
            logger.warning("YouTube channels: @%s — handle not found, skipping", handle)
            continue

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "ignoreerrors": True,
            "playlistend": limit,
            "extractor_args": {"youtubetab": {"skip": ["authcheck"]}},
        }
        if cookies:
            ydl_opts["cookiefile"] = cookies

        fetched = False
        for attempt in range(1, _MAX_429_RETRIES + 1):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                if not info:
                    failures.append(f"@{handle}: no data returned")
                    break
                entries = info.get("entries") or []
                count = 0
                for entry in entries[:limit]:
                    if not entry:
                        continue
                    published_at = _parse_upload_date(entry.get("upload_date"))
                    if published_at < cutoff:
                        continue
                    article = _build_article(entry, source_name)
                    if article:
                        results.append(article)
                        count += 1
                logger.info("YouTube channels: @%s — %d videos", handle, count)
                succeeded += 1
                fetched = True
                break
            except Exception as e:
                msg = str(e)
                if "429" in msg or "Too Many Requests" in msg:
                    wait = min(10 * (2 ** (attempt - 1)), 60)
                    logger.warning("YouTube 429 for @%s (attempt %d/%d) — waiting %ds",
                                   handle, attempt, _MAX_429_RETRIES, wait)
                    if attempt < _MAX_429_RETRIES:
                        time.sleep(wait)
                    else:
                        failures.append(f"@{handle}: 429 after {_MAX_429_RETRIES} retries")
                else:
                    failures.append(f"@{handle}: {msg[:80]}")
                    break

    failed = len(channels) - succeeded
    logger.info("YouTube channels: %d/%d succeeded, %d failed, %d videos total",
                succeeded, len(channels), failed, len(results))
    fetch_state.add(f"YouTube channels: {succeeded}/{len(channels)} fetched, {len(results)} videos")
    if failures:
        logger.warning("YouTube channel failures: %s", "; ".join(failures[:10]))
        fetch_state.add(f"Channel errors: {'; '.join(failures[:5])}")

    return results


# ---------------------------------------------------------------------------
# Fetch keyword search (discovery)
# ---------------------------------------------------------------------------

def _fetch_search_sync(
    keywords: list[str],
    max_results: int,
    cutoff: datetime,
    seen_ids: set[str],
) -> tuple[list[RawArticle], dict[str, str]]:
    """
    Search YouTube by keyword. Returns (articles, discovered_channels).
    discovered_channels: {identifier -> display_name} for new channels found.
    """
    import yt_dlp
    from app.database import get_all_youtube_channel_identifiers

    # Build set of already-known channel identifiers (including blocked)
    known_channels = get_all_youtube_channel_identifiers()

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "ignoreerrors": True,
    }
    cookies = _cookies_file()
    if cookies:
        ydl_opts["cookiefile"] = cookies
        logger.debug("YouTube search: using cookies file")

    results: list[RawArticle] = []
    discovered: dict[str, str] = {}  # identifier -> display name

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for keyword in keywords:
            try:
                info = ydl.extract_info(
                    f"ytsearch{max_results}:{keyword}", download=False
                )
                if not info or "entries" not in info:
                    continue

                for entry in (info["entries"] or []):
                    if not entry:
                        continue
                    vid_id = entry.get("id", "")
                    if not vid_id or vid_id in seen_ids:
                        continue
                    seen_ids.add(vid_id)

                    published_at = _parse_upload_date(entry.get("upload_date"))
                    if published_at < cutoff:
                        continue

                    # Detect new channels from search results
                    ch_id = entry.get("channel_id") or ""
                    ch_handle = entry.get("uploader_id") or ""  # e.g. "@ChannelHandle"
                    ch_name = entry.get("uploader") or entry.get("channel") or ch_handle

                    # Normalise identifier to @handle form when available
                    identifier = ch_handle if ch_handle.startswith("@") else (
                        f"@{ch_handle}" if ch_handle else f"UCid:{ch_id}"
                    )

                    if identifier and identifier not in known_channels:
                        discovered[identifier] = ch_name
                        known_channels.add(identifier)  # Don't register twice in one run

                    article = _build_article(entry, f"YouTube: {keyword}")
                    if article:
                        results.append(article)

            except Exception as e:
                logger.error("YouTube search failed for '%s': %s", keyword, e)

    return results, discovered


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def fetch_youtube() -> list[RawArticle]:
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        logger.error("yt-dlp not installed. Run: pip install yt-dlp")
        return []

    yt_cfg = config.get("sources.youtube", {})

    # Get enabled channels from database only (no static config channels)
    from app.database import get_youtube_channels
    db_channels = [row["identifier"] for row in get_youtube_channels() if row["enabled"]]
    channels = db_channels

    channel_limit = yt_cfg.get("channel_video_limit", 5)
    channel_days_back = yt_cfg.get("channel_days_back", 7)
    keywords = yt_cfg.get("keywords", [])
    max_results = yt_cfg.get("max_results", 10)
    search_days_back = yt_cfg.get("published_after_days", 2)

    channel_cutoff = datetime.now(timezone.utc) - timedelta(days=channel_days_back)
    search_cutoff = datetime.now(timezone.utc) - timedelta(days=search_days_back)

    seen_ids: set[str] = set()

    # --- Phase 1: fetch pinned channels + keyword search concurrently ---
    channel_articles, (search_articles, discovered) = await asyncio.gather(
        asyncio.to_thread(_fetch_channels_sync, channels, channel_limit, channel_cutoff),
        asyncio.to_thread(_fetch_search_sync, keywords, max_results, search_cutoff, seen_ids),
    )

    # Mark channel article IDs as seen so keyword search can't produce dupes
    for a in channel_articles:
        seen_ids.add(a.external_id)

    # Register newly discovered channels (disabled by default)
    if discovered:
        from app.database import register_discovered_channel
        new_count = 0
        for identifier, name in discovered.items():
            result = register_discovered_channel(identifier, name)
            if result:
                new_count += 1
        if new_count:
            logger.info("YouTube: discovered %d new channel(s) — review in Admin", new_count)

    all_articles = channel_articles + search_articles
    if not all_articles:
        logger.info("YouTube: no videos found")
        return []

    # --- Phase 2: fetch transcripts + summarize (skip if already in DB) ---
    from app.summarizer import fetch_transcript_and_summarize
    from app.database import get_existing_summary

    to_summarize = []
    for article in all_articles:
        cached = get_existing_summary(article.external_id)
        if cached:
            article.summary = cached
            logger.debug("YouTube: reusing stored summary for %s", article.external_id)
        else:
            to_summarize.append(article)

    if to_summarize:
        logger.info("YouTube: fetching transcripts for %d new videos…", len(to_summarize))
        summaries = await asyncio.gather(
            *[fetch_transcript_and_summarize(a.external_id, a.title) for a in to_summarize],
            return_exceptions=True,
        )
        for article, summary in zip(to_summarize, summaries):
            if isinstance(summary, Exception):
                logger.error("Transcript error for %s: %s", article.external_id, summary)
            else:
                article.summary = summary or ""

    logger.info("YouTube: %d articles ready", len(all_articles))
    return all_articles
