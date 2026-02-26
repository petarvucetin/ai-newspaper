from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.database import get_articles, db_conn

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _last_fetched_utc() -> str | None:
    """Return last fetch time as UTC ISO string (JS will convert to browser local time)."""
    with db_conn() as con:
        row = con.execute("SELECT MAX(fetched_at) AS ts FROM articles").fetchone()
    raw = row["ts"] if row else None
    return raw  # stored as "YYYY-MM-DD HH:MM:SS" UTC


@router.get("/", response_class=HTMLResponse)
async def newspaper(
    request: Request,
    source: str = Query(default="all"),
):
    source_type = None if source in ("all", "bookmarks") else source
    articles = get_articles(limit=100, source_type=source_type)
    return templates.TemplateResponse(
        "newspaper.html",
        {
            "request": request,
            "articles": articles,
            "active_filter": source,
            "last_fetched_utc": _last_fetched_utc(),
        },
    )
