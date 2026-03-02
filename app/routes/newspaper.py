from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.database import get_articles, get_dismissed_articles, get_comments_for_articles, db_conn

from app import __version__

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
templates.env.globals["app_version"] = __version__


def _last_fetched_utc() -> str | None:
    """Return last fetch time as UTC ISO string (JS will convert to browser local time)."""
    with db_conn() as con:
        row = con.execute("SELECT MAX(fetched_at) AS ts FROM articles").fetchone()
    raw = row["ts"] if row else None
    return raw  # stored as "YYYY-MM-DD HH:MM:SS" UTC


def _split_by_age(articles):
    """Split articles into fresh (<=7 days) and archive (>7 days).

    Archive articles also get an ``old`` flag when >10 days (collapsed in UI).
    """
    now = datetime.now(timezone.utc)
    fresh_cutoff = now - timedelta(days=7)
    old_cutoff = now - timedelta(days=10)

    fresh = []
    archive = []
    for a in articles:
        pub = a["published_at"]
        if not pub:
            fresh.append({"article": a, "old": False})
            continue
        try:
            dt = datetime.strptime(pub, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            fresh.append({"article": a, "old": False})
            continue
        if dt >= fresh_cutoff:
            fresh.append({"article": a, "old": False})
        else:
            archive.append({"article": a, "old": dt < old_cutoff})
    return fresh, archive


def _source_counts() -> dict[str, int]:
    """Count non-dismissed articles per source type."""
    with db_conn() as con:
        rows = con.execute(
            "SELECT s.source_type, COUNT(*) as cnt "
            "FROM articles a JOIN sources s ON a.source_id = s.id "
            "WHERE COALESCE(a.dismissed, 0) = 0 "
            "GROUP BY s.source_type"
        ).fetchall()
    counts = {r["source_type"]: r["cnt"] for r in rows}
    # Merge youtube + youtube_channel
    yt = counts.pop("youtube", 0) + counts.pop("youtube_channel", 0)
    if yt:
        counts["youtube"] = yt
    return counts


def _attach_comments(items: list[dict]) -> None:
    """Attach comments to article dicts in-place."""
    article_ids = [item["article"]["id"] for item in items if item.get("article")]
    if not article_ids:
        return
    comments_map = get_comments_for_articles(article_ids)
    for item in items:
        aid = item["article"]["id"]
        item["comments"] = comments_map.get(aid, [])


@router.get("/", response_class=HTMLResponse)
async def newspaper(
    request: Request,
    source: str = Query(default="all"),
):
    if source == "dismissed":
        articles = get_dismissed_articles()
        fresh = [{"article": a, "old": False} for a in articles]
        archive = []
    else:
        source_type = None if source in ("all", "bookmarks") else source
        articles = get_articles(limit=200, source_type=source_type)
        fresh, archive = _split_by_age(articles)
    _attach_comments(fresh)
    _attach_comments(archive)
    return templates.TemplateResponse(
        "newspaper.html",
        {
            "request": request,
            "fresh_articles": fresh,
            "archive_articles": archive,
            "active_filter": source,
            "last_fetched_utc": _last_fetched_utc(),
            "source_counts": _source_counts(),
        },
    )
