import asyncio
import httpx
import logging
from datetime import datetime, timezone
from app.fetchers.base import RawArticle
from app import config

logger = logging.getLogger(__name__)

_BASE = "https://www.reddit.com/r/{sub}/top.json"
_HEADERS = {"User-Agent": "ai-news-tracker/1.0 (public feed reader)"}


async def fetch_reddit() -> list[RawArticle]:
    reddit_cfg = config.get("sources.reddit", {})
    subreddits = reddit_cfg.get("subreddits", [])
    post_limit = min(reddit_cfg.get("post_limit", 25), 100)
    time_filter = reddit_cfg.get("time_filter", "day")

    # --- Phase 1: fetch post listings ---
    raw_posts: list[dict] = []

    async with httpx.AsyncClient(timeout=15, headers=_HEADERS, follow_redirects=True) as client:
        for sub_name in subreddits:
            name = sub_name.lstrip("r/")
            try:
                resp = await client.get(
                    _BASE.format(sub=name),
                    params={"t": time_filter, "limit": post_limit, "raw_json": "1"},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("Reddit fetch failed for r/%s: %s", name, e)
                continue

            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                post_id = post.get("id", "")
                title = post.get("title", "").strip()
                if not post_id or not title:
                    continue

                created_utc = post.get("created_utc")
                raw_posts.append({
                    "subreddit": name,
                    "source_name": f"r/{name}",
                    "post_id": post_id,
                    "title": title,
                    "url": post.get("url") or f"https://www.reddit.com{post.get('permalink', '')}",
                    "selftext": post.get("selftext", "")[:1500],
                    "author": post.get("author", "[deleted]"),
                    "published_at": datetime.fromtimestamp(created_utc, tz=timezone.utc)
                        if created_utc else datetime.now(timezone.utc),
                    "upvotes": post.get("score", 0),
                    "permalink": post.get("permalink", ""),
                })

    if not raw_posts:
        logger.info("Reddit: no posts found")
        return []

    # --- Phase 2: fetch comments + summarize concurrently ---
    from app.summarizer_reddit import fetch_and_summarize_reddit

    logger.info("Reddit: summarizing %d posts via top comments…", len(raw_posts))
    results = await asyncio.gather(
        *[
            fetch_and_summarize_reddit(
                p["post_id"], p["subreddit"], p["title"], p["selftext"]
            )
            for p in raw_posts
        ],
        return_exceptions=True,
    )

    articles: list[RawArticle] = []
    for post, result in zip(raw_posts, results):
        if isinstance(result, Exception):
            logger.error("Summarize failed for %s: %s", post["post_id"], result)
            summary, num_comments = post["selftext"][:400], 0
        else:
            summary, num_comments = result

        article = RawArticle(
            source_name=post["source_name"],
            external_id=post["post_id"],
            title=post["title"],
            url=post["url"],
            summary=summary,
            author=post["author"],
            published_at=post["published_at"],
            thumbnail_url="",
            upvotes=post["upvotes"],
            num_comments=num_comments,
        )
        articles.append(article)

    logger.info("Reddit: %d articles ready", len(articles))
    return articles
