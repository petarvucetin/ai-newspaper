"""
Fetch top relevant comments for articles from Reddit, Hacker News, and YouTube.

Runs as a post-insert pipeline step. For each newly inserted article,
fetches the top 3 comments sorted by community score and filters out
short or deleted comments.
"""
import asyncio
import html
import logging
import os
import re

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_HEADERS_REDDIT = {"User-Agent": "ai-news-tracker/1.0 (public feed reader)"}
_MAX_COMMENTS = 3
_MIN_COMMENT_LEN = 20
_SEMAPHORE = asyncio.Semaphore(3)


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode entities."""
    return re.sub(r"<[^>]+>", "", html.unescape(text)).strip()


def _truncate(text: str, max_len: int = 200) -> str:
    """Truncate to max_len, adding ellipsis if needed."""
    text = " ".join(text.split())  # collapse whitespace
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "\u2026"


async def _fetch_reddit_comments(post_id: str, subreddit: str) -> list[dict]:
    """Fetch top comments from a Reddit post, sorted by score."""
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
    try:
        async with _SEMAPHORE:
            async with httpx.AsyncClient(
                timeout=15, headers=_HEADERS_REDDIT, follow_redirects=True
            ) as client:
                resp = await client.get(
                    url, params={"limit": 10, "sort": "top", "raw_json": "1"}
                )
                resp.raise_for_status()
                data = resp.json()
    except Exception as e:
        logger.debug("Reddit comments fetch failed for %s: %s", post_id, e)
        return []

    if not isinstance(data, list) or len(data) < 2:
        return []

    comments = []
    for child in data[1].get("data", {}).get("children", []):
        d = child.get("data", {})
        body = d.get("body", "").strip()
        if not body or body in ("[deleted]", "[removed]") or len(body) < _MIN_COMMENT_LEN:
            continue
        permalink = d.get("permalink", "")
        comments.append({
            "author": d.get("author", ""),
            "body": _truncate(body),
            "score": d.get("score", 0),
            "comment_url": f"https://www.reddit.com{permalink}" if permalink else "",
        })

    comments = [c for c in comments if c["score"] > 0]
    comments.sort(key=lambda c: c["score"], reverse=True)
    return comments[:_MAX_COMMENTS]


async def _fetch_hn_comments(story_id: str) -> list[dict]:
    """Fetch top comments from an HN story via Algolia API."""
    url = "https://hn.algolia.com/api/v1/search"
    try:
        async with _SEMAPHORE:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    url, params={"tags": f"comment,story_{story_id}", "hitsPerPage": 10}
                )
                resp.raise_for_status()
                data = resp.json()
    except Exception as e:
        logger.debug("HN comments fetch failed for %s: %s", story_id, e)
        return []

    comments = []
    for hit in data.get("hits", []):
        text = _strip_html(hit.get("comment_text", ""))
        if not text or len(text) < _MIN_COMMENT_LEN:
            continue
        comment_id = hit.get("objectID", "")
        comments.append({
            "author": hit.get("author", ""),
            "body": _truncate(text),
            "score": hit.get("points") or 0,
            "comment_url": (
                f"https://news.ycombinator.com/item?id={comment_id}" if comment_id else ""
            ),
        })

    return comments[:_MAX_COMMENTS]


async def _fetch_youtube_comments(video_id: str) -> list[dict]:
    """Fetch top comments from a YouTube video via Data API v3."""
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        return []

    url = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": 10,
        "order": "relevance",
        "textFormat": "plainText",
        "key": api_key,
    }
    try:
        async with _SEMAPHORE:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
    except Exception as e:
        logger.debug("YouTube comments fetch failed for %s: %s", video_id, e)
        return []

    comments = []
    for item in data.get("items", []):
        snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        text = snippet.get("textDisplay", "").strip()
        if not text or len(text) < _MIN_COMMENT_LEN:
            continue
        author = snippet.get("authorDisplayName", "")
        likes = snippet.get("likeCount", 0)
        comment_id = item.get("id", "")
        comments.append({
            "author": author,
            "body": _truncate(text),
            "score": likes,
            "comment_url": (
                f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"
                if comment_id else ""
            ),
        })

    comments = [c for c in comments if c["score"] > 0]
    comments.sort(key=lambda c: c["score"], reverse=True)
    return comments[:_MAX_COMMENTS]


async def fetch_comments_batch(articles: list[dict]) -> dict[int, list[dict]]:
    """Fetch comments for a batch of articles.

    Args:
        articles: List of dicts with keys: id, external_id, source_type, identifier.

    Returns:
        Mapping of article_id -> list of comment dicts.
    """
    results: dict[int, list[dict]] = {}

    async def _fetch_one(article: dict):
        source_type = article["source_type"]
        external_id = article["external_id"]
        identifier = article["identifier"]

        if source_type == "reddit":
            comments = await _fetch_reddit_comments(external_id, identifier)
        elif source_type == "hackernews":
            comments = await _fetch_hn_comments(external_id)
        elif source_type in ("youtube", "youtube_channel"):
            comments = await _fetch_youtube_comments(external_id)
        else:
            comments = []

        results[article["id"]] = comments

    tasks = [_fetch_one(a) for a in articles]
    done = await asyncio.gather(*tasks, return_exceptions=True)
    for article, result in zip(articles, done):
        if isinstance(result, Exception):
            logger.error("Comment fetch failed for article %d: %s", article["id"], result)
            results.setdefault(article["id"], [])

    return results
