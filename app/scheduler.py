import asyncio
import logging
from difflib import SequenceMatcher
from datetime import datetime, timezone
from app.database import db_conn, get_sources, purge_old_dismissed
from app.scoring.relevancy import score_article
from app.scoring.classifier import classify_new_articles
from app.fetchers.hackernews import fetch_hackernews
from app.fetchers.reddit import fetch_reddit
from app.fetchers.youtube import fetch_youtube
from app.fetchers.base import RawArticle
from app.fetch_state import state as fetch_state

logger = logging.getLogger(__name__)

_fetch_lock = asyncio.Lock()

_SIMILARITY_THRESHOLD = 0.85  # titles must be ≥85% similar to be considered duplicates


def _similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= _SIMILARITY_THRESHOLD


def _dedup_by_title(
    articles: list[RawArticle],
    existing_titles: list[str] | None = None,
) -> list[RawArticle]:
    """
    Cluster articles whose titles are highly similar and keep only the one
    with the most upvotes from each cluster. Also drops articles too similar
    to any title in existing_titles (already in the DB).
    """
    existing_lower = [t.lower() for t in (existing_titles or [])]
    kept: list[RawArticle] = []
    used = [False] * len(articles)

    for i, a in enumerate(articles):
        if used[i]:
            continue
        # Skip if very similar to an already-stored article
        if any(_similar(a.title, ex) for ex in existing_lower):
            used[i] = True
            continue
        cluster = [a]
        used[i] = True
        for j in range(i + 1, len(articles)):
            if used[j]:
                continue
            if _similar(a.title, articles[j].title):
                cluster.append(articles[j])
                used[j] = True
        best = max(cluster, key=lambda x: x.upvotes)
        kept.append(best)

    return kept


async def run_fetch() -> dict:
    """Run all fetchers, score articles, insert to DB. Returns stats."""
    async with _fetch_lock:
        return await _run_fetch_inner()


async def _run_fetch_inner() -> dict:
    fetch_state.reset()
    fetch_state.add("Starting fetch pipeline…")
    logger.info("Starting fetch pipeline at %s", datetime.now(timezone.utc).isoformat())

    sources_rows = get_sources()
    source_map: dict[str, tuple[int, float]] = {
        row["name"]: (row["id"], row["weight"]) for row in sources_rows
    }
    # Also map by identifier so channel articles (source_name=@handle) resolve correctly
    for row in sources_rows:
        if row["identifier"] and row["identifier"] not in source_map:
            source_map[row["identifier"]] = (row["id"], row["weight"])

    # Run all three fetchers concurrently with per-fetcher progress
    fetch_state.add("Fetching HackerNews, Reddit, YouTube in parallel…")

    async def _hn():
        fetch_state.add("⏳ HackerNews: fetching…")
        result = await fetch_hackernews()
        fetch_state.add(f"✓ HackerNews: {len(result)} articles")
        return result

    async def _reddit():
        fetch_state.add("⏳ Reddit: fetching posts + comments…")
        result = await fetch_reddit()
        fetch_state.add(f"✓ Reddit: {len(result)} articles")
        return result

    async def _youtube():
        fetch_state.add("⏳ YouTube: fetching videos + transcripts…")
        result = await fetch_youtube()
        fetch_state.add(f"✓ YouTube: {len(result)} articles")
        return result

    results = await asyncio.gather(_hn(), _reddit(), _youtube(), return_exceptions=True)

    all_articles: list[RawArticle] = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("Fetcher raised exception: %s", r)
            fetch_state.add(f"✗ Fetcher error: {r}")
        else:
            all_articles.extend(r)

    # Deduplicate Reddit articles with similar titles — keep highest upvotes
    from app.database import get_recent_reddit_titles
    reddit_articles  = [a for a in all_articles if a.source_name.startswith("r/")]
    other_articles   = [a for a in all_articles if not a.source_name.startswith("r/")]
    existing_titles  = get_recent_reddit_titles(days=3)
    reddit_deduped   = _dedup_by_title(reddit_articles, existing_titles)
    dropped = len(reddit_articles) - len(reddit_deduped)
    if dropped:
        fetch_state.add(f"⚡ Merged {dropped} near-duplicate Reddit title(s)")
    all_articles = other_articles + reddit_deduped

    fetch_state.add(f"Scoring and saving {len(all_articles)} articles…")

    inserted = 0
    skipped = 0

    from app.database import upsert_article
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
            num_comments=article.num_comments,
        )
        if ok:
            inserted += 1
        else:
            skipped += 1

    # --- Fetch top comments for new articles ---
    from app.database import get_articles_needing_comments, insert_comments
    from app.fetchers.comments import fetch_comments_batch

    articles_for_comments = get_articles_needing_comments()
    if articles_for_comments:
        fetch_state.add(f"💬 Fetching comments for {len(articles_for_comments)} articles…")
        comments_map = await fetch_comments_batch(articles_for_comments)
        total_comments = 0
        for aid, comments in comments_map.items():
            total_comments += insert_comments(aid, comments)
        fetch_state.add(f"✓ Stored {total_comments} comments across {len(comments_map)} articles")
        logger.info("Stored %d comments for %d articles", total_comments, len(comments_map))

    # --- Auto-dismiss classifier ---
    from app.database import get_dismissed_titles, auto_dismiss_articles

    dismissed_titles = get_dismissed_titles(days=30)
    if dismissed_titles and inserted > 0:
        fetch_state.add(f"🔍 Running dismiss classifier ({len(dismissed_titles)} dismiss patterns)…")

        # Get newly inserted articles (not yet dismissed, fetched in last hour)
        with db_conn() as con:
            new_rows = con.execute(
                """SELECT id, title FROM articles
                   WHERE COALESCE(dismissed, 0) = 0
                     AND fetched_at >= datetime('now', '-1 hour')
                   ORDER BY id DESC""",
            ).fetchall()

        new_articles = [{"id": r["id"], "title": r["title"]} for r in new_rows]

        if new_articles:
            result = await classify_new_articles(dismissed_titles, new_articles)

            if result["patterns_found"]:
                fetch_state.add(f"📋 Patterns: {', '.join(result['patterns_found'][:5])}")

            if result["dismiss"]:
                ids_to_dismiss = [d["id"] for d in result["dismiss"]]
                count = auto_dismiss_articles(ids_to_dismiss)
                reasons = "; ".join(f"{d['id']}: {d.get('reason', '?')}" for d in result["dismiss"][:10])
                fetch_state.add(f"🚫 Auto-dismissed {count} article(s): {reasons}")
                logger.info("Auto-dismissed %d articles: %s", count, reasons)
            else:
                fetch_state.add("✓ Classifier: no articles to dismiss")
    elif not dismissed_titles:
        fetch_state.add("ℹ No dismiss history yet — classifier skipped")

    purged = purge_old_dismissed()
    if purged:
        fetch_state.add(f"🗑 Purged {purged} dismissed articles older than 7 days")

    fetch_state.finish(inserted, skipped, len(all_articles))
    fetch_state.add(f"✓ Done — {inserted} new, {skipped} skipped ({len(all_articles)} total)")
    logger.info("Fetch complete: %d new, %d skipped", inserted, skipped)
    return {"inserted": inserted, "skipped": skipped, "total": len(all_articles)}


def setup_scheduler(app):
    """Wire APScheduler into FastAPI lifespan."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app import config
    from app.database import get_setting

    default_time = config.get("schedule.fetch_time", "07:00")
    fetch_time = get_setting("schedule.fetch_time", default_time)
    auto_enabled = get_setting("schedule.auto_enabled", "1") == "1"
    hour, minute = map(int, fetch_time.split(":"))

    scheduler = AsyncIOScheduler()
    job = scheduler.add_job(run_fetch, "cron", hour=hour, minute=minute, id="daily_fetch")
    if not auto_enabled:
        job.pause()
    app.state.scheduler = scheduler
    return scheduler


def reschedule(app, fetch_time: str, enabled: bool) -> None:
    """Update the daily fetch job time and enabled state at runtime."""
    from app.database import set_setting
    set_setting("schedule.fetch_time", fetch_time)
    set_setting("schedule.auto_enabled", "1" if enabled else "0")

    scheduler = app.state.scheduler
    hour, minute = map(int, fetch_time.split(":"))
    scheduler.reschedule_job("daily_fetch", trigger="cron", hour=hour, minute=minute)
    job = scheduler.get_job("daily_fetch")
    if enabled:
        job.resume()
    else:
        job.pause()
