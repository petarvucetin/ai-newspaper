"""
Fetch top Reddit comments and produce a TL;DR via Claude Haiku.
Uses Reddit's public JSON API — no credentials needed.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "ai-news-tracker/1.0 (public feed reader)"}
_TOP_COMMENTS = 10
_MAX_COMMENT_CHARS = 6_000


def _api_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "")


async def fetch_top_comments(post_id: str, subreddit: str) -> list[str]:
    """Fetch top-level comments for a Reddit post, sorted by score."""
    import httpx
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
    try:
        async with httpx.AsyncClient(timeout=15, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(url, params={"limit": _TOP_COMMENTS, "sort": "top", "raw_json": "1"})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.debug("Failed to fetch comments for %s: %s", post_id, e)
        return []

    # data[1] is the comments listing
    if not isinstance(data, list) or len(data) < 2:
        return []

    comments = []
    for child in data[1].get("data", {}).get("children", []):
        body = child.get("data", {}).get("body", "").strip()
        if body and body != "[deleted]" and body != "[removed]":
            comments.append(body)
        if len(comments) >= _TOP_COMMENTS:
            break

    return comments


async def summarize_reddit(title: str, selftext: str, comments: list[str]) -> str:
    """
    Build a TL;DR from post body + top comments using Claude Haiku.
    Falls back to selftext excerpt if no API key.
    """
    api_key = _api_key()

    # Build context: prefer comments, fall back to selftext
    has_content = bool(selftext.strip() or comments)
    if not has_content:
        return ""

    if not api_key:
        # Fallback: use selftext or first comment excerpt
        source = selftext.strip() or (comments[0] if comments else "")
        return source[:400].rstrip() + ("…" if len(source) > 400 else "")

    try:
        import anthropic
    except ImportError:
        return selftext[:400]

    # Build the context block
    parts = []
    if selftext.strip():
        parts.append(f"Post body:\n{selftext.strip()[:1500]}")
    if comments:
        parts.append("Top comments:\n" + "\n\n".join(
            f"• {c[:300]}" for c in comments[:_TOP_COMMENTS]
        ))

    context = "\n\n".join(parts)
    if len(context) > _MAX_COMMENT_CHARS:
        context = context[:_MAX_COMMENT_CHARS]

    prompt = (
        f'Reddit post title: "{title}"\n\n'
        f"{context}\n\n"
        "Write a TL;DR summary of this Reddit post and its discussion in 2-3 sentences. "
        "Capture the main point of the post and the key sentiment or insights from the comments. "
        "Be direct and concise. Do not include a heading or label like 'TL;DR:'."
    )

    def _call() -> str:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    try:
        return await asyncio.to_thread(_call)
    except Exception as e:
        logger.error("Reddit summarization failed for '%s': %s", title[:50], e)
        return selftext[:400] if selftext else ""


async def fetch_and_summarize_reddit(
    post_id: str, subreddit: str, title: str, selftext: str
) -> tuple[str, int]:
    """
    Returns (summary, num_comments).
    num_comments is the actual comment count from the post page.
    """
    import httpx
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
    num_comments = 0
    try:
        async with httpx.AsyncClient(timeout=15, headers=_HEADERS, follow_redirects=True) as client:
            resp = await client.get(url, params={"limit": _TOP_COMMENTS, "sort": "top", "raw_json": "1"})
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, list) and len(data) >= 1:
            post_data = data[0].get("data", {}).get("children", [{}])[0].get("data", {})
            num_comments = post_data.get("num_comments", 0)

        comments = []
        if len(data) >= 2:
            for child in data[1].get("data", {}).get("children", []):
                body = child.get("data", {}).get("body", "").strip()
                if body and body not in ("[deleted]", "[removed]"):
                    comments.append(body)
                if len(comments) >= _TOP_COMMENTS:
                    break
    except Exception as e:
        logger.debug("Comment fetch failed for %s: %s", post_id, e)
        comments = []

    summary = await summarize_reddit(title, selftext, comments)
    return summary, num_comments
