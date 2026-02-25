#!/usr/bin/env python3
"""Manually trigger a full fetch."""
import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, seed_keywords, seed_sources
from app import config
from app.scheduler import run_fetch


async def main():
    init_db()
    seed_keywords(config.get("keyword_weights", {}))
    seed_sources(config.get("sources", {}))
    stats = await run_fetch()
    print(f"Fetch complete: {stats['inserted']} new, {stats['skipped']} skipped, {stats['total']} total")


if __name__ == "__main__":
    asyncio.run(main())
