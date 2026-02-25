#!/usr/bin/env python3
"""
Backfill view counts for YouTube articles that have upvotes = 0.
Run once:  python3 scripts/backfill_views.py
"""
import sys, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yt_dlp
from app.database import db_conn


def fetch_view_counts(video_ids: list[str]) -> dict[str, int]:
    """Fetch view counts for a batch of video IDs via yt-dlp."""
    results: dict[str, int] = {}
    ydl_opts = {"quiet": True, "extract_flat": True, "skip_download": True, "ignoreerrors": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Fetch in batches of 50 via a playlist-style URL
        for vid_id in video_ids:
            try:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={vid_id}", download=False
                )
                if info:
                    results[vid_id] = info.get("view_count") or 0
            except Exception:
                pass
    return results


def main():
    with db_conn() as con:
        rows = con.execute(
            """SELECT a.id, a.external_id FROM articles a
               JOIN sources s ON a.source_id = s.id
               WHERE s.source_type IN ('youtube', 'youtube_channel') AND a.upvotes = 0"""
        ).fetchall()

    if not rows:
        print("No YouTube articles need view count backfill.")
        return

    print(f"Backfilling view counts for {len(rows)} articles…")
    video_ids = [r["external_id"] for r in rows]
    id_map = {r["external_id"]: r["id"] for r in rows}

    view_counts = fetch_view_counts(video_ids)
    updated = 0
    with db_conn() as con:
        for vid_id, views in view_counts.items():
            if views > 0:
                con.execute("UPDATE articles SET upvotes = ? WHERE id = ?",
                            (views, id_map[vid_id]))
                updated += 1

    print(f"Done: {updated} view counts updated.")


if __name__ == "__main__":
    main()
