#!/usr/bin/env python3
"""
Backfill summaries for YouTube articles that have an empty summary.
Run once after setting ANTHROPIC_API_KEY in .env:

    python3 scripts/backfill_summaries.py
"""
import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from app.database import db_conn
from app.summarizer import fetch_transcript_and_summarize


async def main():
    with db_conn() as con:
        rows = con.execute(
            """SELECT a.id, a.external_id, a.title
               FROM articles a
               JOIN sources s ON a.source_id = s.id
               WHERE s.source_type IN ('youtube', 'youtube_channel')
                 AND (a.summary IS NULL OR LENGTH(a.summary) < 500)
               ORDER BY a.fetched_at DESC"""
        ).fetchall()

    if not rows:
        print("No YouTube articles with empty summaries found.")
        return

    print(f"Found {len(rows)} YouTube articles without summaries. Backfilling…\n")
    ok = skipped = 0

    for row in rows:
        print(f"  [{row['id']}] {row['title'][:60]}")
        summary = None
        for attempt in range(3):
            try:
                summary = await fetch_transcript_and_summarize(row['external_id'], row['title'])
                break
            except Exception as e:
                err = type(e).__name__
                if attempt < 2:
                    print(f"         ↻ {err}, retrying in 10s…")
                    await asyncio.sleep(10)
                else:
                    print(f"         ✗ {err} after 3 attempts")
        await asyncio.sleep(3)  # pace requests
        if summary:
            with db_conn() as con:
                con.execute(
                    "UPDATE articles SET summary = ? WHERE id = ?",
                    (summary, row['id']),
                )
            print(f"         ✓ {len(summary)} chars")
            ok += 1
        else:
            print(f"         — no transcript available")
            skipped += 1

    print(f"\nDone: {ok} summaries written, {skipped} skipped (no transcript).")


if __name__ == "__main__":
    asyncio.run(main())
