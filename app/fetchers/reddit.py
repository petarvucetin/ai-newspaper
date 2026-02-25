import httpx
import logging
from datetime import datetime, timezone
from app.fetchers.base import RawArticle
from app import config

logger = logging.getLogger(__name__)

# Reddit's public JSON API — works for any public subreddit, no auth needed.
_BASE = "https://www.reddit.com/r/{sub}/top.json"
_HEADERS = {"User-Agent": "ai-news-tracker/1.0 (public feed reader)"}


async def fetch_reddit() -> list[RawArticle]:
    reddit_cfg = config.get("sources.reddit", {})
    subreddits = reddit_cfg.get("subreddits", [])
    post_limit = min(reddit_cfg.get("post_limit", 25), 100)  # API max is 100
    time_filter = reddit_cfg.get("time_filter", "day")

    articles: list[RawArticle] = []

    async with httpx.AsyncClient(timeout=15, headers=_HEADERS, follow_redirects=True) as client:
        for sub_name in subreddits:
            name = sub_name.lstrip("r/")
            source_name = f"r/{name}"
            url = _BASE.format(sub=name)
            try:
                resp = await client.get(
                    url,
                    params={"t": time_filter, "limit": post_limit, "raw_json": "1"},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("Reddit fetch failed for r/%s: %s", name, e)
                continue

            posts = data.get("data", {}).get("children", [])
            for child in posts:
                post = child.get("data", {})
                post_id = post.get("id", "")
                title = post.get("title", "").strip()
                if not post_id or not title:
                    continue

                post_url = post.get("url") or f"https://www.reddit.com{post.get('permalink', '')}"
                created_utc = post.get("created_utc")
                published_at = (
                    datetime.fromtimestamp(created_utc, tz=timezone.utc)
                    if created_utc
                    else datetime.now(timezone.utc)
                )
                thumbnail = post.get("thumbnail", "")
                if not thumbnail.startswith("http"):
                    thumbnail = ""

                articles.append(RawArticle(
                    source_name=source_name,
                    external_id=post_id,
                    title=title,
                    url=post_url,
                    summary=post.get("selftext", "")[:500],
                    author=post.get("author", "[deleted]"),
                    published_at=published_at,
                    thumbnail_url=thumbnail,
                    upvotes=post.get("score", 0),
                ))

    logger.info("Reddit: fetched %d articles", len(articles))
    return articles
