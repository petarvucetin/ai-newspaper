from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.scoring.feedback import apply_rating
from app.database import delete_source

router = APIRouter()


class RatingRequest(BaseModel):
    score: int = Field(..., ge=1, le=5)


@router.post("/rate/{article_id}")
async def rate_article(article_id: int, body: RatingRequest):
    try:
        apply_rating(article_id, body.score)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok", "article_id": article_id, "score": body.score}


@router.delete("/source/{source_id}")
async def remove_source(source_id: int):
    try:
        delete_source(source_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok", "source_id": source_id}
