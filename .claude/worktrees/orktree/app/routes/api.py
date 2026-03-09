from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query
from app.database import (
    get_articles, get_dismissed_articles, get_comments_for_articles, db_conn
)

router = APIRouter(prefix="/api")


def _split_by_age(articles):
    now = datetime.now(timezone.utc)
    fresh_cutoff = now - timedelta(days=7)
    old_cutoff = now - timedelta(days=10)
    fresh, archive = [], []
    for a in articles:
        pub = a["published_at"]
        if not pub:
            fresh.append({"article": _row_to_dict(a), "old": False})
            continue
        try:
            dt = datetime.strptime(pub, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            fresh.append({"article": _row_to_dict(a), "old": False})
            continue
        if dt >= fresh_cutoff:
            fresh.append({"article": _row_to_dict(a), "old": False})
        else:
            archive.append({"article": _row_to_dict(a), "old": dt < old_cutoff})
    return fresh, archive


def _row_to_dict(row) -> dict:
    return dict(row)


def _attach_comments(items: list[dict]) -> None:
    article_ids = [item["article"]["id"] for item in items if item.get("article")]
    if not article_ids:
        return
    comments_map = get_comments_for_articles(article_ids)
    for item in items:
        aid = item["article"]["id"]
        item["comments"] = comments_map.get(aid, [])


def _source_counts() -> dict[str, int]:
    with db_conn() as con:
        rows = con.execute(
            "SELECT s.source_type, COUNT(*) as cnt "
            "FROM articles a JOIN sources s ON a.source_id = s.id "
            "WHERE COALESCE(a.dismissed, 0) = 0 "
            "GROUP BY s.source_type"
        ).fetchall()
    counts = {r["source_type"]: r["cnt"] for r in rows}
    yt = counts.pop("youtube", 0) + counts.pop("youtube_channel", 0)
    if yt:
        counts["youtube"] = yt
    return counts


def _last_fetched_utc() -> str | None:
    with db_conn() as con:
        row = con.execute("SELECT MAX(fetched_at) AS ts FROM articles").fetchone()
    return row["ts"] if row else None


@router.get("/articles")
async def api_articles(source: str = Query(default="all")):
    if source == "dismissed":
        articles = get_dismissed_articles()
        fresh = [{"article": _row_to_dict(a), "old": False} for a in articles]
        archive = []
    else:
        source_type = None if source in ("all", "bookmarks") else source
        articles = get_articles(limit=200, source_type=source_type)
        fresh, archive = _split_by_age(articles)
    _attach_comments(fresh)
    _attach_comments(archive)
    from app import __version__
    return {
        "fresh": fresh,
        "archive": archive,
        "active_filter": source,
        "last_fetched_utc": _last_fetched_utc(),
        "source_counts": _source_counts(),
        "version": __version__,
    }


@router.get("/admin/data")
async def api_admin_data():
    """Return all admin page data as JSON."""
    from app.database import (
        get_sources, get_keyword_weights, get_youtube_channels, get_reddit_sources,
        get_setting, get_api_usage_summary,
    )
    from app import config
    from app.routes.admin import _cookies_status, _last_fetched

    all_sources = get_sources()
    sources = [dict(s) for s in all_sources if s["source_type"] not in ("youtube_channel", "reddit")]
    channels = [dict(ch) for ch in get_youtube_channels()]
    reddit_sources = [dict(r) for r in get_reddit_sources()]
    keywords = [dict(kw) for kw in get_keyword_weights()]
    default_time = config.get("schedule.fetch_time", "07:00")
    schedule_time = get_setting("schedule.fetch_time", default_time)
    auto_enabled = get_setting("schedule.auto_enabled", "1") == "1"

    return {
        "sources": sources,
        "channels": channels,
        "reddit_sources": reddit_sources,
        "keywords": keywords,
        "last_fetched": _last_fetched(),
        "schedule_time": schedule_time,
        "auto_enabled": auto_enabled,
        "cookies_status": _cookies_status(),
        "api_usage": get_api_usage_summary(),
    }
