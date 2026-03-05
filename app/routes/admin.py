import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pathlib import Path
from app import config
from app.database import (
    get_youtube_channels, get_reddit_sources,
    add_youtube_channel, add_reddit_subreddit, db_conn, get_setting, set_setting,
    add_keyword_weight, delete_keyword_weight, add_source, delete_source,
)

_COOKIES_PATH = Path(__file__).parent.parent.parent / "youtube_cookies.txt"


def _cookies_status() -> dict:
    """Return info about the YouTube cookies file."""
    if not _COOKIES_PATH.exists() or _COOKIES_PATH.stat().st_size == 0:
        return {"exists": False, "age_days": None, "warning": True}
    mtime = datetime.fromtimestamp(_COOKIES_PATH.stat().st_mtime, tz=timezone.utc)
    age_days = (datetime.now(timezone.utc) - mtime).days
    return {
        "exists": True,
        "age_days": age_days,
        "warning": age_days >= 7,
    }


def _last_fetched() -> str | None:
    with db_conn() as con:
        row = con.execute("SELECT MAX(fetched_at) AS ts FROM articles").fetchone()
    return row["ts"] if row else None

router = APIRouter()
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


@router.post("/admin/source/{source_id}/weight")
async def update_source_weight(
    source_id: int,
    weight: float = Form(...),
    _: str = Depends(require_admin),
):
    weight = max(0.1, min(3.0, weight))
    with db_conn() as con:
        con.execute("UPDATE sources SET weight = ? WHERE id = ?", (weight, source_id))
    return {"ok": True}


@router.post("/admin/source/{source_id}/toggle")
async def toggle_source(source_id: int, _: str = Depends(require_admin)):
    with db_conn() as con:
        con.execute(
            "UPDATE sources SET enabled = NOT enabled WHERE id = ?", (source_id,)
        )
    return {"ok": True}


@router.post("/admin/keyword/{keyword_id}/weight")
async def update_keyword_weight(
    keyword_id: int,
    weight: float = Form(...),
    _: str = Depends(require_admin),
):
    weight = max(0.1, min(5.0, weight))
    with db_conn() as con:
        con.execute("UPDATE keyword_weights SET weight = ? WHERE id = ?", (weight, keyword_id))
    return {"ok": True}


@router.post("/admin/weights/save")
async def bulk_save_weights(request: Request, _: str = Depends(require_admin)):
    """Save all source and keyword weights in one request."""
    body = await request.json()
    updated = 0
    with db_conn() as con:
        for item in body.get("sources", []):
            w = max(0.1, min(3.0, float(item["weight"])))
            con.execute("UPDATE sources SET weight = ? WHERE id = ?", (w, int(item["id"])))
            updated += 1
        for item in body.get("keywords", []):
            w = max(0.1, min(5.0, float(item["weight"])))
            con.execute("UPDATE keyword_weights SET weight = ? WHERE id = ?", (w, int(item["id"])))
            updated += 1
    return {"ok": True, "updated": updated}


@router.post("/admin/channel/{source_id}/pin")
async def pin_channel(source_id: int, _: str = Depends(require_admin)):
    """Enable (pin) a discovered channel so it's fetched directly."""
    with db_conn() as con:
        con.execute("UPDATE sources SET enabled = 1 WHERE id = ? AND source_type = 'youtube_channel'", (source_id,))
    return {"ok": True}


@router.post("/admin/channel/{source_id}/unpin")
async def unpin_channel(source_id: int, _: str = Depends(require_admin)):
    """Disable a channel (keep record but stop fetching it directly)."""
    with db_conn() as con:
        con.execute("UPDATE sources SET enabled = 0 WHERE id = ? AND source_type = 'youtube_channel'", (source_id,))
    return {"ok": True}


@router.post("/admin/channel/{source_id}/delete")
async def delete_channel(source_id: int, _: str = Depends(require_admin)):
    """Block a channel permanently so it never reappears."""
    with db_conn() as con:
        con.execute(
            "UPDATE sources SET blocked = 1, enabled = 0 WHERE id = ? AND source_type = 'youtube_channel'",
            (source_id,),
        )
    return {"ok": True}


@router.post("/admin/schedule")
async def update_schedule(
    request: Request,
    fetch_time: str = Form(...),
    auto_enabled: str = Form(default="0"),
    _: str = Depends(require_admin),
):
    from app.scheduler import reschedule
    enabled = auto_enabled == "1"
    reschedule(request.app, fetch_time, enabled)
    return {"ok": True}


@router.post("/admin/channel/add")
async def add_channel(channel: str = Form(...), _: str = Depends(require_admin)):
    handle = channel.strip().lstrip("@")
    # Validate the channel handle exists on YouTube
    from app.fetchers.youtube import validate_channel_handle
    import asyncio
    valid = await asyncio.to_thread(validate_channel_handle, handle)
    if not valid:
        return {"ok": False, "error": f"Channel @{handle} not found on YouTube"}
    added = add_youtube_channel(handle)
    return {"ok": True, "added": added}


@router.post("/admin/reddit/add")
async def add_subreddit(subreddit: str = Form(...), _: str = Depends(require_admin)):
    name = subreddit.strip()
    added = add_reddit_subreddit(name)
    return {"ok": True, "added": added}


@router.post("/admin/reddit/{source_id}/toggle")
async def toggle_reddit(source_id: int, _: str = Depends(require_admin)):
    with db_conn() as con:
        con.execute("UPDATE sources SET enabled = NOT enabled WHERE id = ? AND source_type = 'reddit'", (source_id,))
    return {"ok": True}


@router.post("/admin/reddit/{source_id}/delete")
async def delete_reddit(source_id: int, _: str = Depends(require_admin)):
    """Block a subreddit permanently so it never reappears."""
    with db_conn() as con:
        con.execute(
            "UPDATE sources SET blocked = 1, enabled = 0 WHERE id = ? AND source_type = 'reddit'",
            (source_id,),
        )
    return {"ok": True}


@router.post("/admin/keyword/add")
async def add_keyword(
    keyword: str = Form(...),
    weight: float = Form(default=1.0),
    _: str = Depends(require_admin),
):
    keyword = keyword.strip()
    added = add_keyword_weight(keyword, weight)
    return {"ok": True, "added": added}


@router.post("/admin/keyword/{keyword_id}/delete")
async def delete_keyword(keyword_id: int, _: str = Depends(require_admin)):
    delete_keyword_weight(keyword_id)
    return {"ok": True}


@router.post("/admin/source/add")
async def add_source_route(
    name: str = Form(...),
    source_type: str = Form(...),
    identifier: str = Form(...),
    weight: float = Form(default=1.0),
    _: str = Depends(require_admin),
):
    added = add_source(name, source_type, identifier, weight)
    return {"ok": True, "added": added}


@router.post("/admin/source/{source_id}/delete")
async def delete_source_route(source_id: int, _: str = Depends(require_admin)):
    delete_source(source_id)
    return {"ok": True}


@router.post("/admin/cookies/upload")
async def upload_cookies(
    cookies_file: UploadFile = File(...),
    _: str = Depends(require_admin),
):
    raw = await cookies_file.read()
    if not raw.strip():
        return {"ok": False, "error": "Cookies file is empty"}
    # Decode robustly — handles UTF-16 (with BOM) that some browsers produce
    for enc in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
        try:
            content = raw.decode(enc)
            break
        except (UnicodeDecodeError, Exception):
            continue
    else:
        return {"ok": False, "error": "Could not decode cookies file"}
    # Re-encode as plain UTF-8 (what yt-dlp expects)
    _COOKIES_PATH.write_text(content, encoding="utf-8")
    return {"ok": True}


@router.post("/admin/cookies/delete")
async def delete_cookies(_: str = Depends(require_admin)):
    if _COOKIES_PATH.exists():
        _COOKIES_PATH.unlink()
    return {"ok": True}


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
