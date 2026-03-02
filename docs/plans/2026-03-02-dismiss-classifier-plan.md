# Dismiss-Based Article Classifier Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an LLM-powered classifier that analyzes dismissed articles and auto-dismisses new articles matching the same patterns during each fetch, plus show relevancy scores on article cards.

**Architecture:** New `app/scoring/classifier.py` module makes a single Claude Haiku call after articles are inserted during a fetch. It gathers dismissed article titles as negative examples, sends them with the new article batch, and marks matched articles as auto-dismissed. Integrates into the existing fetch pipeline in `app/scheduler.py` as a post-insert step.

**Tech Stack:** Python 3, anthropic SDK (already installed), SQLite, Jinja2 templates.

**Design doc:** `docs/plans/2026-03-02-dismiss-classifier-design.md`

---

### Task 1: Add `auto_dismissed` Column Migration

**Files:**
- Modify: `app/database.py:79-93` (init_db function)

**Step 1: Add the migration**

In `app/database.py`, inside the `init_db()` function, after the existing `dismissed_at` migration (line 88), add:

```python
        if "auto_dismissed" not in cols:
            con.execute("ALTER TABLE articles ADD COLUMN auto_dismissed BOOLEAN DEFAULT 0")
```

This goes right after:
```python
        if "dismissed_at" not in cols:
            con.execute("ALTER TABLE articles ADD COLUMN dismissed_at DATETIME")
```

**Step 2: Verify the migration runs**

Start the app briefly to trigger `init_db()`:
```bash
cd D:/AI/projects/ai-news-tracking && python -c "from app.database import init_db; init_db()"
```

Expected: No errors. The column should now exist.

**Step 3: Verify the column exists**

```bash
cd D:/AI/projects/ai-news-tracking && python -c "
import sqlite3
con = sqlite3.connect('data/news.db')
cols = {row[1] for row in con.execute('PRAGMA table_info(articles)')}
assert 'auto_dismissed' in cols, f'Missing! Got: {cols}'
print('OK: auto_dismissed column exists')
"
```

**Step 4: Commit**

```bash
git add app/database.py
git commit -m "feat: add auto_dismissed column to articles table"
```

---

### Task 2: Add Database Helper Queries

**Files:**
- Modify: `app/database.py` — add two new functions at the bottom

**Step 1: Add `get_dismissed_titles` function**

Add this function at the bottom of `app/database.py` (after `upsert_article`):

```python
def get_dismissed_titles(days: int = 30) -> list[str]:
    """Return titles of manually dismissed articles from the last N days."""
    with db_conn() as con:
        rows = con.execute(
            """SELECT title FROM articles
               WHERE dismissed = 1 AND COALESCE(auto_dismissed, 0) = 0
                 AND dismissed_at >= datetime('now', ?)
               ORDER BY dismissed_at DESC""",
            (f"-{days} days",),
        ).fetchall()
    return [r["title"] for r in rows]


def auto_dismiss_articles(article_ids: list[int]) -> int:
    """Mark articles as auto-dismissed. Returns count updated."""
    if not article_ids:
        return 0
    with db_conn() as con:
        placeholders = ",".join("?" * len(article_ids))
        cur = con.execute(
            f"""UPDATE articles
                SET dismissed = 1, auto_dismissed = 1, dismissed_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders}) AND COALESCE(dismissed, 0) = 0""",
            article_ids,
        )
        return cur.rowcount
```

**Step 2: Test the helpers work**

```bash
cd D:/AI/projects/ai-news-tracking && python -c "
from app.database import init_db, get_dismissed_titles, auto_dismiss_articles
init_db()
titles = get_dismissed_titles(30)
print(f'Found {len(titles)} dismissed titles')
if titles:
    print(f'Sample: {titles[0][:80]}')
# Don't actually auto-dismiss anything — just test the function exists
count = auto_dismiss_articles([])
print(f'auto_dismiss_articles([]) returned: {count}')
print('OK')
"
```

Expected: Prints count of dismissed titles and 0 for empty list.

**Step 3: Commit**

```bash
git add app/database.py
git commit -m "feat: add get_dismissed_titles and auto_dismiss_articles helpers"
```

---

### Task 3: Create the Classifier Module

**Files:**
- Create: `app/scoring/classifier.py`

**Step 1: Write the classifier**

Create `app/scoring/classifier.py` with the following content:

```python
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

    try:
        async with _ANTHROPIC_SEMAPHORE:
            raw, input_tok, output_tok = await asyncio.to_thread(_call_api)

        from app.database import log_api_usage
        log_api_usage("claude-haiku-4-5-20251001", input_tok, output_tok, "dismiss_classifier")
        logger.info("Dismiss classifier: %d input, %d output tokens", input_tok, output_tok)

        # Parse JSON response — handle markdown code fences
        text = raw.strip()
        if text.startswith("```"):
            # Strip ```json ... ``` wrapper
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
```

**Step 2: Verify module imports cleanly**

```bash
cd D:/AI/projects/ai-news-tracking && python -c "from app.scoring.classifier import classify_new_articles, _build_prompt; print('OK')"
```

**Step 3: Quick smoke test of prompt building**

```bash
cd D:/AI/projects/ai-news-tracking && python -c "
from app.scoring.classifier import _build_prompt
prompt = _build_prompt(
    ['Tutorial: Python for beginners', 'Enterprise AI in Banking'],
    [{'id': 1, 'title': 'MCP Server Deep Dive'}, {'id': 2, 'title': 'Python 101 Course'}],
)
assert 'Tutorial: Python for beginners' in prompt
assert '[ID 1] MCP Server Deep Dive' in prompt
assert 'CONSERVATIVE' in prompt
print('OK: prompt builds correctly')
"
```

**Step 4: Commit**

```bash
git add app/scoring/classifier.py
git commit -m "feat: add LLM-powered dismiss classifier module"
```

---

### Task 4: Integrate Classifier into Fetch Pipeline

**Files:**
- Modify: `app/scheduler.py:116-161` — add classify step after article insertion

**Step 1: Add the classify step**

In `app/scheduler.py`, after the article insertion loop (after line 153, `skipped += 1`) and before the purge step (line 155), add the classifier integration.

First, add the import at the top of the file (after the existing imports around line 10):

```python
from app.scoring.classifier import classify_new_articles
```

Then, after the insertion loop ends (after the `for article in all_articles:` block, around line 153), insert:

```python
    # --- Auto-dismiss classifier ---
    from app.database import get_dismissed_titles, auto_dismiss_articles

    dismissed_titles = get_dismissed_titles(days=30)
    if dismissed_titles and inserted > 0:
        fetch_state.add(f"🔍 Running dismiss classifier ({len(dismissed_titles)} dismiss patterns)…")

        # Get newly inserted articles (not yet dismissed, fetched in last hour)
        with db_conn() as con:
            new_rows = con.execute(
                """SELECT id, title FROM articles
                   WHERE COALESCE(dismissed, 0) = 0
                     AND fetched_at >= datetime('now', '-1 hour')
                   ORDER BY id DESC""",
            ).fetchall()

        new_articles = [{"id": r["id"], "title": r["title"]} for r in new_rows]

        if new_articles:
            result = await classify_new_articles(dismissed_titles, new_articles)

            if result["patterns_found"]:
                fetch_state.add(f"📋 Patterns: {', '.join(result['patterns_found'][:5])}")

            if result["dismiss"]:
                ids_to_dismiss = [d["id"] for d in result["dismiss"]]
                count = auto_dismiss_articles(ids_to_dismiss)
                reasons = "; ".join(f"{d['id']}: {d.get('reason', '?')}" for d in result["dismiss"][:10])
                fetch_state.add(f"🚫 Auto-dismissed {count} article(s): {reasons}")
                logger.info("Auto-dismissed %d articles: %s", count, reasons)
            else:
                fetch_state.add("✓ Classifier: no articles to dismiss")
    elif not dismissed_titles:
        fetch_state.add("ℹ No dismiss history yet — classifier skipped")
```

**Step 2: Verify the scheduler still imports**

```bash
cd D:/AI/projects/ai-news-tracking && python -c "from app.scheduler import run_fetch; print('OK')"
```

**Step 3: Commit**

```bash
git add app/scheduler.py
git commit -m "feat: integrate dismiss classifier into fetch pipeline"
```

---

### Task 5: Show Relevancy Score on Article Cards

**Files:**
- Modify: `app/templates/newspaper.html:43-70` — add relevancy label to card macro
- Modify: `app/static/style.css` — add `.relevancy-label` style

**Step 1: Add CSS for relevancy label**

Add this to `app/static/style.css` after the `.score-label` rule (around line 382):

```css
/* ---- Relevancy label (inline) ---- */
.relevancy-label {
  font-family: var(--font-sans);
  font-size: 0.62rem;
  font-weight: 600;
  color: var(--ink-muted);
  background: var(--cream-dark);
  padding: 0.1rem 0.35rem;
  border-radius: 2px;
  white-space: nowrap;
}
.relevancy-label.high { color: var(--score-high); }
.relevancy-label.mid  { color: var(--score-mid); }
```

**Step 2: Add the relevancy label to the card macro**

In `app/templates/newspaper.html`, inside the `article_card` macro, in the `.article-meta-top` div (around line 49-68), add the relevancy label after the source badge:

Find this block (lines 49-50):
```jinja2
      <div class="article-meta-top">
        {{ source_badge(article.source_type, article.source_name) }}
```

Replace with:
```jinja2
      <div class="article-meta-top">
        {{ source_badge(article.source_type, article.source_name) }}
        {% if article.relevancy_score is not none and article.relevancy_score > 0 %}
          {%- set rpct = (article.relevancy_score * 100)|int -%}
          <span class="relevancy-label {% if rpct >= 70 %}high{% elif rpct >= 40 %}mid{% endif %}"
                title="Relevancy: {{ '%.2f'|format(article.relevancy_score) }}">{{ rpct }}%</span>
        {% endif %}
```

**Step 3: Verify visually**

Open the app and check that each article card now shows a small percentage label (e.g., "72%") next to the source badge. High scores should be green, mid should be gold.

**Step 4: Commit**

```bash
git add app/static/style.css app/templates/newspaper.html
git commit -m "feat: show relevancy score percentage on article cards"
```

---

### Task 6: Show "Auto" Badge on Auto-Dismissed Articles

**Files:**
- Modify: `app/templates/newspaper.html` — add "Auto" badge in dismissed view
- Modify: `app/static/style.css` — add `.auto-badge` style

**Step 1: Add CSS for auto-dismiss badge**

Add to `app/static/style.css`:

```css
/* ---- Auto-dismiss badge ---- */
.auto-badge {
  font-family: var(--font-sans);
  font-size: 0.6rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ink-muted);
  background: var(--cream-dark);
  border: 1px solid var(--rule);
  padding: 0.1rem 0.35rem;
  border-radius: 2px;
}
```

**Step 2: Add badge to card macro**

In `app/templates/newspaper.html`, inside the `article_card` macro, in the `.article-meta-top` div, add after the source badge (and after the new relevancy label from Task 5):

```jinja2
        {% if article.auto_dismissed %}
        <span class="auto-badge" title="Auto-dismissed by classifier">Auto</span>
        {% endif %}
```

**Step 3: Verify**

In the dismissed view (`/?source=dismissed`), auto-dismissed articles should show an "Auto" badge. Manually dismissed articles should not.

**Step 4: Commit**

```bash
git add app/static/style.css app/templates/newspaper.html
git commit -m "feat: show Auto badge on auto-dismissed articles in dismissed view"
```

---

### Task 7: Update Restore to Clear auto_dismissed Flag

**Files:**
- Modify: `app/routes/dismiss.py:19-28` — clear `auto_dismissed` on restore

**Step 1: Update the restore endpoint**

In `app/routes/dismiss.py`, update the restore SQL (line 22) to also clear `auto_dismissed`:

Replace:
```python
            "UPDATE articles SET dismissed = 0, dismissed_at = NULL WHERE id = ?",
```

With:
```python
            "UPDATE articles SET dismissed = 0, dismissed_at = NULL, auto_dismissed = 0 WHERE id = ?",
```

**Step 2: Verify**

```bash
cd D:/AI/projects/ai-news-tracking && python -c "
from app.routes.dismiss import router
print('OK: dismiss router imports cleanly')
"
```

**Step 3: Commit**

```bash
git add app/routes/dismiss.py
git commit -m "fix: clear auto_dismissed flag when restoring an article"
```

---

### Task 8: End-to-End Verification

**Step 1: Run the app**

```bash
cd D:/AI/projects/ai-news-tracking && python -m uvicorn app.main:app --port 8001
```

**Step 2: Verify existing functionality works**

- Open `http://localhost:8001` — articles should display normally
- Relevancy scores should show as percentage labels on each card
- Dismiss an article — should still work with undo
- Check `/?source=dismissed` — should show dismissed articles
- Bookmark, star rating, keyboard nav should all still work

**Step 3: Test the classifier (manual fetch)**

- Go to `http://localhost:8001/admin`
- Click "Fetch Now"
- Watch the fetch log — should show:
  - "Running dismiss classifier (N dismiss patterns)..."
  - "Patterns: ..." (the patterns it found)
  - "Auto-dismissed N article(s): ..." OR "no articles to dismiss"
- After fetch completes, go to `/?source=dismissed`
- Any auto-dismissed articles should show the "Auto" badge

**Step 4: Final commit**

If any fixes were needed during verification:
```bash
git add -A
git commit -m "fix: end-to-end verification fixes for dismiss classifier"
```
