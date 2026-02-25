import math
from datetime import datetime, timezone
from app import config


def _get_keyword_weights_from_db() -> dict[str, float]:
    """Load keyword weights from DB (lazy import to avoid circular deps)."""
    from app.database import db_conn
    with db_conn() as con:
        rows = con.execute("SELECT keyword, weight FROM keyword_weights").fetchall()
    return {row["keyword"]: row["weight"] for row in rows}


def keyword_score(title: str, keyword_weights: dict[str, float]) -> float:
    """Sum weights of matching keywords in title, capped at configured max."""
    cap = config.get("scoring.keyword_score_cap", 10.0)
    title_lower = title.lower()
    total = 0.0
    for kw, weight in keyword_weights.items():
        if kw in title_lower:
            total += weight
    return min(total, cap)


def recency_multiplier(published_at: datetime) -> float:
    cfg = config.get("scoring.recency_multipliers", {})
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = (now - published_at).total_seconds() / 3600
    if age_hours < 24:
        return cfg.get("under_24h", 1.5)
    elif age_hours < 48:
        return cfg.get("under_48h", 1.2)
    return cfg.get("older", 1.0)


def compute_display_score(
    title: str,
    published_at: datetime,
    upvotes: int,
    source_weight: float,
    keyword_weights: dict[str, float],
) -> float:
    ks = keyword_score(title, keyword_weights)
    rm = recency_multiplier(published_at)
    log_upvotes = math.log10(max(upvotes, 0) + 10)
    return ks * source_weight * rm * log_upvotes


def score_article(
    title: str,
    published_at: datetime,
    upvotes: int,
    source_weight: float,
) -> tuple[float, float]:
    """Returns (relevancy_score, display_score). Loads keyword weights from DB."""
    kw_weights = _get_keyword_weights_from_db()
    ks = keyword_score(title, kw_weights)
    ds = compute_display_score(title, published_at, upvotes, source_weight, kw_weights)
    return ks, ds
