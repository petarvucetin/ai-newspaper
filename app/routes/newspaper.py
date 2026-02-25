from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.database import get_articles

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


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
        },
    )
