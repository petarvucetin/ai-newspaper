# YouTube Channel Fetch Reliability — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make YouTube channel fetching reliable across 43+ channels by adding rate limiting, verbose error logging, and channel handle validation.

**Architecture:** Rewrite `_fetch_channels_sync` to create a fresh yt-dlp instance per channel with a 5s delay between requests, retry on 429, and route yt-dlp output to Python logging. Add a lightweight `_validate_channel_handle` function used by both the fetcher and the Admin add-channel endpoint.

**Tech Stack:** yt-dlp, httpx (already a dependency), Python logging

---

### Task 1: Rate Limiting — Rewrite `_fetch_channels_sync`

**Files:**
- Modify: `app/fetchers/youtube.py:51-93`

**Step 1: Rewrite the function**

Replace `_fetch_channels_sync` with this implementation:

```python
_CHANNEL_DELAY = 5        # seconds between channel fetches
_MAX_429_RETRIES = 3      # retry attempts on HTTP 429

def _fetch_channels_sync(channels: list[str], limit: int, cutoff: datetime) -> list[RawArticle]:
    """Fetch latest videos from each channel via yt-dlp with rate limiting."""
    import time
    import yt_dlp

    cookies = _cookies_file()
    results: list[RawArticle] = []
    succeeded = 0
    failures: list[str] = []  # "handle: reason" strings

    for idx, handle in enumerate(channels):
        handle = handle.lstrip("@")
        source_name = f"@{handle}"
        url = f"https://www.youtube.com/@{handle}/videos"

        if idx > 0:
            time.sleep(_CHANNEL_DELAY)

        logger.info("YouTube channels: fetching @%s (%d/%d)…", handle, idx + 1, len(channels))

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
    if failures:
        logger.warning("YouTube channel failures: %s", "; ".join(failures[:10]))

    return results
```

**Step 2: Verify**

Run a manual fetch from Admin UI. Check Docker logs for per-channel progress messages.

**Step 3: Commit**

```
git add app/fetchers/youtube.py
git commit -m "feat: add rate limiting and retry to YouTube channel fetcher"
```

---

### Task 2: Surface Failures in Fetch State Log

**Files:**
- Modify: `app/fetchers/youtube.py:51` (the function from Task 1)
- Modify: `app/fetchers/youtube.py:180` (`fetch_youtube`)

**Step 1: Pass fetch_state into _fetch_channels_sync**

Add `from app.fetch_state import state as fetch_state` at module top.

In `_fetch_channels_sync`, after the loop ends, add:

```python
    # Surface results in Admin UI fetch log
    from app.fetch_state import state as fetch_state
    fetch_state.add(f"YouTube channels: {succeeded}/{len(channels)} fetched, {len(results)} videos")
    if failures:
        fetch_state.add(f"Channel errors: {'; '.join(failures[:5])}")
```

**Step 2: Commit**

```
git add app/fetchers/youtube.py
git commit -m "feat: surface YouTube channel fetch errors in Admin UI"
```

---

### Task 3: Channel Handle Validation

**Files:**
- Modify: `app/fetchers/youtube.py` — add `_validate_channel_handle` function
- Modify: `app/routes/admin.py:142-146` — validate on add

**Step 1: Add validation function to youtube.py**

Add after the imports section:

```python
def _validate_channel_handle(handle: str) -> bool:
    """Check if a YouTube channel handle exists via a lightweight HEAD request."""
    import httpx
    handle = handle.lstrip("@")
    url = f"https://www.youtube.com/@{handle}"
    try:
        resp = httpx.head(url, follow_redirects=True, timeout=10,
                          headers={"User-Agent": "Mozilla/5.0"})
        return resp.status_code == 200
    except Exception:
        return False  # Network error — assume invalid
```

**Step 2: Add validation to admin add_channel endpoint**

In `app/routes/admin.py`, update the `add_channel` function:

```python
@router.post("/admin/channel/add")
async def add_channel(channel: str = Form(...), _: str = Depends(require_admin)):
    handle = channel.strip()
    # Validate the channel handle exists on YouTube
    from app.fetchers.youtube import _validate_channel_handle
    import asyncio
    valid = await asyncio.to_thread(_validate_channel_handle, handle)
    if not valid:
        return {"ok": False, "error": f"Channel @{handle.lstrip('@')} not found on YouTube"}
    added = add_youtube_channel(handle)
    return {"ok": True, "added": added}
```

**Step 3: Add validation during fetch for untested channels**

In `_fetch_channels_sync` (the function from Task 1), add validation before the yt-dlp call. Insert right after `logger.info("YouTube channels: fetching @%s...")`:

```python
        # Quick validation for channels that have never been fetched
        if not _validate_channel_handle(handle):
            failures.append(f"@{handle}: handle not found on YouTube")
            logger.warning("YouTube channels: @%s — handle not found, skipping", handle)
            continue
```

**Step 4: Commit**

```
git add app/fetchers/youtube.py app/routes/admin.py
git commit -m "feat: validate YouTube channel handles on add and during fetch"
```

---

### Task 4: Final Integration Verification

**Step 1:** Trigger a manual fetch from Admin UI.

**Step 2:** Monitor Docker logs — confirm:
- Per-channel progress: `"fetching @handle (3/43)"`
- 5-second gaps between channels
- Success/failure summary at end
- Failures surfaced in Admin fetch log

**Step 3:** Try adding an invalid channel handle in Admin — confirm error returned.

**Step 4:** Commit the design doc:

```
git add docs/plans/
git commit -m "docs: add YouTube fetch reliability design and plan"
```
