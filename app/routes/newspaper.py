from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime, timezone
from app.database import get_articles, db_conn

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTHS = ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]


def _last_fetched_label() -> str | None:
    """Return last fetch time formatted in local time, e.g. 'Wednesday, February 25, 2026 07:00'."""
    with db_conn() as con:
        row = con.execute("SELECT MAX(fetched_at) AS ts FROM articles").fetchone()
    raw = row["ts"] if row else None
    if not raw:
        return None
    # DB stores UTC without tzinfo — attach UTC, convert to local
    dt_utc = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    dt_local = dt_utc.astimezone()
    return (
        f"{_WEEKDAYS[dt_local.weekday()]}, "
        f"{_MONTHS[dt_local.month - 1]} {dt_local.day}, "
        f"{dt_local.year} "
        f"{dt_local.hour:02d}:{dt_local.minute:02d}"
    )


@router.get("/", response_class=HTMLResponse)
async def newspaper(
    request: Request,
    source: str = Query(default="all"),
):
    source_type = None if source == "all" else source
    articles = get_articles(limit=100, source_type=source_type)
    return templates.TemplateResponse(
        "newspaper.html",
        {
            "request": request,
            "articles": articles,
            "active_filter": source,
            "edition_date": _last_fetched_label(),
        },
    )
