from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime, timezone
from app.database import get_articles, db_conn

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _last_fetched() -> str | None:
    """Return the most recent fetched_at timestamp across all articles."""
    with db_conn() as con:
        row = con.execute("SELECT MAX(fetched_at) AS ts FROM articles").fetchone()
    return row["ts"] if row else None


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
            "last_fetched": _last_fetched(),
        },
    )
