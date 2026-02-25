import asyncio
import httpx
import logging
from datetime import datetime, timezone
from app.fetchers.base import RawArticle
from app import config

logger = logging.getLogger(__name__)

_BASE = "https://www.reddit.com/r/{sub}/top.json"
_HEADERS = {"User-Agent": "ai-news-tracker/1.0 (public feed reader)"}

# Max concurrent comment-fetch requests to avoid 429s
_COMMENT_SEMAPHORE = asyncio.Semaphore(3)
# Seconds between subreddit listing requests
_LISTING_DELAY = 1.0


async def _get_with_retry(client: httpx.AsyncClient, url: str, params: dict, retries: int = 3) -> httpx.Response:
    """GET with exponential backoff on 429."""
    for attempt in range(retries):
        resp = await client.get(url, params=params)
        if resp.status_code == 429:
            wait = 2 ** attempt * 2  # 2s, 4s, 8s
            logger.warning("Reddit 429 on %s — retrying in %ds", url, wait)
            await asyncio.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp


async def fetch_reddit() -> list[RawArticle]:
    reddit_cfg = config.get("sources.reddit", {})
    subreddits = reddit_cfg.get("subreddits", [])
    post_limit = min(reddit_cfg.get("post_limit", 25), 100)
    time_filter = reddit_cfg.get("time_filter", "day")

    # --- Phase 1: fetch post listings (sequential with delay) ---
    raw_posts: list[dict] = []

    async with httpx.AsyncClient(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
        for i, sub_name in enumerate(subreddits):
            if i > 0:
                await asyncio.sleep(_LISTING_DELAY)
            name = sub_name.lstrip("r/")
            try:
                resp = await _get_with_retry(
                    client,
                    _BASE.format(sub=name),
                    params={"t": time_filter, "limit": post_limit, "raw_json": "1"},
                )
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

    # --- Phase 2: fetch comments + summarize (skip if already in DB) ---
    from app.summarizer_reddit import fetch_and_summarize_reddit
    from app.database import get_existing_summary

    cached_results: dict[str, tuple[str, int]] = {}
    to_summarize = []
    for post in raw_posts:
        cached = get_existing_summary(post["post_id"])
        if cached:
            cached_results[post["post_id"]] = (cached, 0)
            logger.debug("Reddit: reusing stored summary for %s", post["post_id"])
        else:
            to_summarize.append(post)

    async def _throttled(post: dict):
        async with _COMMENT_SEMAPHORE:
            return await fetch_and_summarize_reddit(
                post["post_id"], post["subreddit"], post["title"], post["selftext"]
            )

    if to_summarize:
        logger.info("Reddit: summarizing %d new posts via top comments…", len(to_summarize))
        results = await asyncio.gather(
            *[_throttled(p) for p in to_summarize],
            return_exceptions=True,
        )
        for post, result in zip(to_summarize, results):
            if isinstance(result, Exception):
                logger.error("Summarize failed for %s: %s", post["post_id"], result)
                cached_results[post["post_id"]] = (post["selftext"][:400], 0)
            else:
                cached_results[post["post_id"]] = result

    articles: list[RawArticle] = []
    for post in raw_posts:
        summary, num_comments = cached_results.get(post["post_id"], (post["selftext"][:400], 0))

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
