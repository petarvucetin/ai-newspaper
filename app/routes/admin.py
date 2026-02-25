import secrets
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pathlib import Path
from app import config
from app.database import (
    get_sources, get_keyword_weights, get_youtube_channels, get_reddit_sources,
    add_youtube_channel, add_reddit_subreddit, db_conn,
)


def _last_fetched() -> str | None:
    with db_conn() as con:
        row = con.execute("SELECT MAX(fetched_at) AS ts FROM articles").fetchone()
    return row["ts"] if row else None

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    admin_user = config.get("admin.username", "admin")
    admin_pass = config.get("admin.password", "changeme")
    ok_user = secrets.compare_digest(credentials.username.encode(), admin_user.encode())
    ok_pass = secrets.compare_digest(credentials.password.encode(), admin_pass.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@router.get("/admin", response_class=HTMLResponse)
async def admin_get(request: Request, _: str = Depends(require_admin), msg: str = ""):
    all_sources = get_sources()
    sources = [s for s in all_sources if s["source_type"] not in ("youtube_channel", "reddit")]
    channels = get_youtube_channels()
    reddit_sources = get_reddit_sources()
    keywords = get_keyword_weights()
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "sources": sources,
            "channels": channels,
            "reddit_sources": reddit_sources,
            "keywords": keywords,
            "msg": msg,
            "last_fetched": _last_fetched(),
        },
    )


@router.post("/admin/source/{source_id}/weight")
async def update_source_weight(
    source_id: int,
    weight: float = Form(...),
    _: str = Depends(require_admin),
):
    weight = max(0.1, min(3.0, weight))
    with db_conn() as con:
        con.execute("UPDATE sources SET weight = ? WHERE id = ?", (weight, source_id))
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/source/{source_id}/toggle")
async def toggle_source(source_id: int, _: str = Depends(require_admin)):
    with db_conn() as con:
        con.execute(
            "UPDATE sources SET enabled = NOT enabled WHERE id = ?", (source_id,)
        )
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/keyword/{keyword_id}/weight")
async def update_keyword_weight(
    keyword_id: int,
    weight: float = Form(...),
    _: str = Depends(require_admin),
):
    weight = max(0.1, min(5.0, weight))
    with db_conn() as con:
        con.execute("UPDATE keyword_weights SET weight = ? WHERE id = ?", (weight, keyword_id))
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/channel/{source_id}/pin")
async def pin_channel(source_id: int, _: str = Depends(require_admin)):
    """Enable (pin) a discovered channel so it's fetched directly."""
    with db_conn() as con:
        con.execute("UPDATE sources SET enabled = 1 WHERE id = ? AND source_type = 'youtube_channel'", (source_id,))
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/channel/{source_id}/unpin")
async def unpin_channel(source_id: int, _: str = Depends(require_admin)):
    """Disable a channel (keep record but stop fetching it directly)."""
    with db_conn() as con:
        con.execute("UPDATE sources SET enabled = 0 WHERE id = ? AND source_type = 'youtube_channel'", (source_id,))
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/channel/{source_id}/delete")
async def delete_channel(source_id: int, _: str = Depends(require_admin)):
    """Remove a discovered channel record entirely."""
    with db_conn() as con:
        con.execute("DELETE FROM sources WHERE id = ? AND source_type = 'youtube_channel'", (source_id,))
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/channel/add")
async def add_channel(channel: str = Form(...), _: str = Depends(require_admin)):
    handle = channel.strip()
    added = add_youtube_channel(handle)
    msg = f"Added {handle}" if added else f"{handle} already exists"
    return RedirectResponse(f"/admin?msg={msg}", status_code=303)


@router.post("/admin/reddit/add")
async def add_subreddit(subreddit: str = Form(...), _: str = Depends(require_admin)):
    name = subreddit.strip()
    added = add_reddit_subreddit(name)
    msg = f"Added r/{name.lstrip('r/').lstrip('/')}" if added else f"r/{name.lstrip('r/').lstrip('/')} already exists"
    return RedirectResponse(f"/admin?msg={msg}", status_code=303)


@router.post("/admin/reddit/{source_id}/toggle")
async def toggle_reddit(source_id: int, _: str = Depends(require_admin)):
    with db_conn() as con:
        con.execute("UPDATE sources SET enabled = NOT enabled WHERE id = ? AND source_type = 'reddit'", (source_id,))
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/reddit/{source_id}/delete")
async def delete_reddit(source_id: int, _: str = Depends(require_admin)):
    with db_conn() as con:
        con.execute("DELETE FROM sources WHERE id = ? AND source_type = 'reddit'", (source_id,))
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/fetch-now")
async def fetch_now_admin(_: str = Depends(require_admin)):
    from app.scheduler import run_fetch
    from app.fetch_state import state as fetch_state
    import asyncio
    if fetch_state.status == "running":
        return {"status": "already_running"}
    asyncio.create_task(run_fetch())
    return {"status": "started"}


@router.get("/admin/fetch-status")
async def fetch_status(_: str = Depends(require_admin)):
    from app.fetch_state import state as fetch_state
    return fetch_state.to_dict()
