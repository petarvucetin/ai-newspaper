from fastapi import APIRouter, HTTPException
from app.database import db_conn

router = APIRouter()


@router.delete("/dismiss/{article_id}")
async def dismiss_article(article_id: int):
    with db_conn() as con:
        cur = con.execute(
            "UPDATE articles SET dismissed = 1, dismissed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (article_id,)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Article not found")
    return {"status": "ok", "article_id": article_id}


@router.post("/restore/{article_id}")
async def restore_article(article_id: int):
    with db_conn() as con:
        cur = con.execute(
            "UPDATE articles SET dismissed = 0, dismissed_at = NULL WHERE id = ?",
            (article_id,)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Article not found")
    return {"status": "ok", "article_id": article_id}
