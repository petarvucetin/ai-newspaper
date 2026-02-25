from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.scoring.feedback import apply_rating

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
