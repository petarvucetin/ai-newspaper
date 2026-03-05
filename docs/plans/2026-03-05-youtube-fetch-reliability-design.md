# YouTube Channel Fetch Reliability

**Date:** 2026-03-05
**Problem:** Only 3 of 43 enabled YouTube channels are being fetched. yt-dlp silently fails on the rest, likely due to YouTube rate limiting.

## Solution 1: Rate Limiting with Delays

**File:** `app/fetchers/youtube.py` — `_fetch_channels_sync`

- Add 5-second delay between each channel fetch
- Retry on 429 errors with exponential backoff (3 attempts: 10s, 20s, 40s)
- Create a fresh YoutubeDL instance per channel
- Log progress: `"YouTube channels: fetching @handle (3/43)..."`

## Solution 2: Debug Logging for Failures

**File:** `app/fetchers/youtube.py` — `_fetch_channels_sync`

- Replace `quiet: True` with a custom yt-dlp logger that routes to Python logging at DEBUG level
- Track per-channel success/failure counts
- Log summary: `"YouTube channels: 38/43 succeeded, 5 failed: @CNN (429), @CBS19 (not found)"`
- Surface failures in fetch state log (visible in Admin UI)

## Solution 3: Channel Handle Validation

**Files:** `app/fetchers/youtube.py`, `app/routes/admin.py`

- New `_validate_channel_handle(handle)` function: HEAD request to `https://www.youtube.com/@{handle}`, returns True/False
- During fetch: skip channels with 0 articles that fail validation, log warning
- Admin add channel: validate before inserting, reject invalid handles
- Keep validation lightweight (HEAD request, not full yt-dlp extraction)

## Integration

All three solutions compose: the fetcher validates handles (3), delays between channels (1), and logs exactly what fails (2). The Admin UI shows per-channel errors in the fetch progress log.
