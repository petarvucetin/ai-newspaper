"""
LLM-powered dismiss classifier.

Analyzes manually dismissed articles to find patterns, then identifies
which newly fetched articles match those patterns and should be auto-dismissed.
Runs once per fetch as a post-insert step.
"""
import asyncio
import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_ANTHROPIC_SEMAPHORE = asyncio.Semaphore(1)


def _api_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "")


def _build_prompt(dismissed_titles: list[str], new_articles: list[dict]) -> str:
    """Build the classification prompt.

    Args:
        dismissed_titles: Titles the user has manually dismissed.
        new_articles: List of dicts with 'id' and 'title' keys.
    """
    dismissed_block = "\n".join(f"- {t}" for t in dismissed_titles)
    new_block = "\n".join(f"- [ID {a['id']}] {a['title']}" for a in new_articles)

    return (
        "You are a news relevancy classifier for a personal AI news digest.\n\n"
        "The user has MANUALLY dismissed these articles (they find them uninteresting):\n"
        f"{dismissed_block}\n\n"
        "Here are newly fetched articles:\n"
        f"{new_block}\n\n"
        "Analyze the dismissed articles to identify patterns in what the user does NOT want. "
        "Common patterns might include: beginner tutorials, enterprise case studies, "
        "academic papers, business/marketing content, non-technical news, etc.\n\n"
        "For each new article, decide if it clearly matches the dismiss patterns.\n"
        "Be CONSERVATIVE — only dismiss articles that strongly match. When in doubt, KEEP.\n\n"
        "Return valid JSON and nothing else:\n"
        '{"dismiss": [{"id": <int>, "reason": "<10 words max>"}], '
        '"patterns_found": ["<pattern1>", "<pattern2>"]}'
    )


async def classify_new_articles(
    dismissed_titles: list[str],
    new_articles: list[dict],
) -> dict:
    """Call Claude Haiku to classify which new articles should be auto-dismissed.

    Args:
        dismissed_titles: Titles the user has manually dismissed.
        new_articles: List of dicts with 'id' and 'title' keys.

    Returns:
        Dict with 'dismiss' (list of {id, reason}) and 'patterns_found' (list of str).
        Returns empty result if API key missing or call fails.
    """
    if not dismissed_titles or not new_articles:
        return {"dismiss": [], "patterns_found": []}

    api_key = _api_key()
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping dismiss classifier")
        return {"dismiss": [], "patterns_found": []}

    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed — skipping dismiss classifier")
        return {"dismiss": [], "patterns_found": []}

    prompt = _build_prompt(dismissed_titles, new_articles)

    def _call_api() -> tuple[str, int, int]:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip(), msg.usage.input_tokens, msg.usage.output_tokens

    raw = ""
    try:
        async with _ANTHROPIC_SEMAPHORE:
            raw, input_tok, output_tok = await asyncio.to_thread(_call_api)

        from app.database import log_api_usage
        log_api_usage("claude-haiku-4-5-20251001", input_tok, output_tok, "dismiss_classifier")
        logger.info("Dismiss classifier: %d input, %d output tokens", input_tok, output_tok)

        # Parse JSON response — handle markdown code fences
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        result = json.loads(text)

        # Validate structure
        if not isinstance(result.get("dismiss"), list):
            result["dismiss"] = []
        if not isinstance(result.get("patterns_found"), list):
            result["patterns_found"] = []

        # Validate article IDs — only keep IDs that are in our new_articles list
        valid_ids = {a["id"] for a in new_articles}
        result["dismiss"] = [
            d for d in result["dismiss"]
            if isinstance(d, dict) and d.get("id") in valid_ids
        ]

        return result

    except json.JSONDecodeError as e:
        logger.error("Dismiss classifier returned invalid JSON: %s — raw: %s", e, raw[:200])
        return {"dismiss": [], "patterns_found": []}
    except Exception as e:
        logger.error("Dismiss classifier failed: %s", e)
        return {"dismiss": [], "patterns_found": []}
