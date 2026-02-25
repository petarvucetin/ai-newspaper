import logging
from app import config
from app.database import db_conn
from app.scoring.relevancy import _get_keyword_weights_from_db, compute_display_score
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def apply_rating(article_id: int, score: int) -> None:
    """
    1. Insert rating.
    2. Update source.weight and keyword_weights.
    3. Recalculate display_score for unrated articles from same source.
    """
    cfg_fb = config.get("scoring.feedback", {})
    src_delta = cfg_fb.get("source_weight_delta", 0.05)
    kw_delta = cfg_fb.get("keyword_weight_delta", 0.025)
    src_min = cfg_fb.get("source_weight_min", 0.1)
    src_max = cfg_fb.get("source_weight_max", 3.0)
    kw_min = cfg_fb.get("keyword_weight_min", 0.1)
    kw_max = cfg_fb.get("keyword_weight_max", 5.0)

    sentiment = (score - 3) / 2.0  # -1.0 to +1.0

    with db_conn() as con:
        # Insert rating
        con.execute(
            "INSERT INTO ratings (article_id, score) VALUES (?, ?)",
            (article_id, score),
        )

        # Get article title and source_id
        row = con.execute(
            "SELECT title, source_id FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
        if not row:
            logger.warning("apply_rating: article %d not found", article_id)
            return

        title = row["title"]
        source_id = row["source_id"]

        # Update source weight
        src_row = con.execute("SELECT weight FROM sources WHERE id = ?", (source_id,)).fetchone()
        if src_row:
            new_w = max(src_min, min(src_max, src_row["weight"] + src_delta * sentiment))
            con.execute("UPDATE sources SET weight = ? WHERE id = ?", (new_w, source_id))

        # Update keyword weights for matching keywords
        kw_rows = con.execute("SELECT keyword, weight FROM keyword_weights").fetchall()
        title_lower = title.lower()
        for kw_row in kw_rows:
            kw = kw_row["keyword"]
            if kw in title_lower:
                new_kw = max(kw_min, min(kw_max, kw_row["weight"] + kw_delta * sentiment))
                con.execute(
                    "UPDATE keyword_weights SET weight = ?, hits = hits + 1 WHERE keyword = ?",
                    (new_kw, kw),
                )

    # Recalculate display_score for unrated articles from same source
    _recalculate_source_scores(source_id)


def _recalculate_source_scores(source_id: int) -> None:
    """Batch-recalculate display_score for unrated articles from source."""
    kw_weights = _get_keyword_weights_from_db()

    with db_conn() as con:
        src_row = con.execute("SELECT weight FROM sources WHERE id = ?", (source_id,)).fetchone()
        if not src_row:
            return
        source_weight = src_row["weight"]

        # Articles from this source without a rating
        rows = con.execute(
            """SELECT a.id, a.title, a.published_at, a.upvotes
               FROM articles a
               WHERE a.source_id = ?
                 AND a.id NOT IN (SELECT article_id FROM ratings)""",
            (source_id,),
        ).fetchall()

        for row in rows:
            published_at = _parse_dt(row["published_at"])
            ds = compute_display_score(
                row["title"], published_at, row["upvotes"], source_weight, kw_weights
            )
            con.execute(
                "UPDATE articles SET display_score = ? WHERE id = ?", (ds, row["id"])
            )

    logger.debug("Recalculated %d articles for source %d", len(rows), source_id)


def _parse_dt(val) -> datetime:
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(val, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return datetime.now(timezone.utc)
