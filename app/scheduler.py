import asyncio
import logging
from datetime import datetime, timezone
from app.database import db_conn, get_sources
from app.scoring.relevancy import score_article
from app.fetchers.hackernews import fetch_hackernews
from app.fetchers.reddit import fetch_reddit
from app.fetchers.youtube import fetch_youtube
from app.fetchers.base import RawArticle

logger = logging.getLogger(__name__)


async def run_fetch() -> dict:
    """Run all fetchers, score articles, insert to DB. Returns stats."""
    logger.info("Starting fetch pipeline at %s", datetime.now(timezone.utc).isoformat())

    # Load sources into a lookup dict: name -> (id, weight)
    sources_rows = get_sources()
    source_map: dict[str, tuple[int, float]] = {
        row["name"]: (row["id"], row["weight"]) for row in sources_rows
    }

    # Fetch from all sources concurrently
    results = await asyncio.gather(
        fetch_hackernews(),
        fetch_reddit(),
        fetch_youtube(),
        return_exceptions=True,
    )

    all_articles: list[RawArticle] = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("Fetcher raised exception: %s", r)
        else:
            all_articles.extend(r)

    inserted = 0
    skipped = 0

    for article in all_articles:
        source_info = source_map.get(article.source_name)
        if not source_info:
            logger.warning("Unknown source name '%s', skipping", article.source_name)
            continue

        source_id, source_weight = source_info
        relevancy, display = score_article(
            article.title,
            article.published_at,
            article.upvotes,
            source_weight,
        )

        from app.database import upsert_article
        ok = upsert_article(
            source_id=source_id,
            external_id=article.external_id,
            title=article.title,
            url=article.url,
            summary=article.summary,
            author=article.author,
            published_at=article.published_at.strftime("%Y-%m-%d %H:%M:%S"),
            relevancy_score=relevancy,
            display_score=display,
            thumbnail_url=article.thumbnail_url,
            upvotes=article.upvotes,
        )
        if ok:
            inserted += 1
        else:
            skipped += 1

    logger.info("Fetch complete: %d new, %d skipped", inserted, skipped)
    return {"inserted": inserted, "skipped": skipped, "total": len(all_articles)}


def setup_scheduler(app):
    """Wire APScheduler into FastAPI lifespan."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app import config

    fetch_time = config.get("schedule.fetch_time", "07:00")
    hour, minute = map(int, fetch_time.split(":"))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_fetch, "cron", hour=hour, minute=minute, id="daily_fetch")
    app.state.scheduler = scheduler
    return scheduler
