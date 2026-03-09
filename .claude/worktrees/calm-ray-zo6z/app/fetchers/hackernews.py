import httpx
import logging
from datetime import datetime, timedelta, timezone
from app.fetchers.base import RawArticle
from app import config

logger = logging.getLogger(__name__)

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"


async def fetch_hackernews() -> list[RawArticle]:
    hn_cfg = config.get("sources.hackernews", {})

    # Get enabled keywords from database only
    from app.database import get_sources, db_conn
    with db_conn() as con:
        rows = con.execute(
            "SELECT identifier FROM sources WHERE source_type = 'hackernews' AND enabled = 1 AND COALESCE(blocked, 0) = 0"
        ).fetchall()
    keywords = [row["identifier"] for row in rows]
    hits_per_page = hn_cfg.get("hits_per_page", 20)
    days_back = hn_cfg.get("days_back", 2)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    cutoff_ts = int(cutoff.timestamp())

    articles: list[RawArticle] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(timeout=15) as client:
        for keyword in keywords:
            try:
                resp = await client.get(ALGOLIA_URL, params={
                    "query": keyword,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{cutoff_ts}",
                    "hitsPerPage": hits_per_page,
                })
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("HackerNews fetch failed for '%s': %s", keyword, e)
                continue

            for hit in data.get("hits", []):
                hn_id = hit.get("objectID", "")
                if not hn_id or hn_id in seen_ids:
                    continue
                seen_ids.add(hn_id)

                url = hit.get("url") or f"https://news.ycombinator.com/item?id={hn_id}"
                title = hit.get("title", "").strip()
                if not title:
                    continue

                created_ts = hit.get("created_at_i")
                if created_ts:
                    published_at = datetime.fromtimestamp(created_ts, tz=timezone.utc)
                else:
                    published_at = datetime.now(timezone.utc)

                articles.append(RawArticle(
                    source_name=f"HN: {keyword}",
                    external_id=hn_id,
                    title=title,
                    url=url,
                    summary=hit.get("story_text") or "",
                    author=hit.get("author", ""),
                    published_at=published_at,
                    upvotes=hit.get("points") or 0,
                ))

    logger.info("HackerNews: fetched %d articles", len(articles))
    return articles
