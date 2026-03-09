# Dismiss-Based Article Classifier — Design

**Date:** 2026-03-02
**Approach:** LLM-powered classifier that analyzes dismissed articles and auto-dismisses new articles matching the same patterns during each fetch.

---

## Problem

Dismissals are a dead end — the user dismisses ~14% of articles (73 of 530), but this signal is never used to improve future filtering. Only 16 star ratings (3%) feed back into weight adjustments. The keyword/upvote scoring model cannot distinguish "Claude Code MCP tutorial" (wanted) from "Claude Code Full Course for Beginners" (unwanted) because both match the same keywords.

## Observed dismiss patterns (from data)

- Tutorial/beginner content (e.g., "FULL COURSE for beginners", "7 Hour Course in 27 Minutes")
- Enterprise/business case studies ("Claude in Legal", "transforming financial services")
- Academic/research papers ("From GRPO to SAMPO: Solving Training Collapse")
- Generic AI industry news without technical depth

## Solution

### Pipeline integration

Current: Fetch → Dedup → Score → Insert → Purge
New:     Fetch → Dedup → Score → Insert → **Classify & Auto-dismiss** → Purge

### Classify step

1. Query all manually dismissed article titles from last 30 days
2. Query all newly inserted articles from the current fetch batch
3. Single Claude Haiku API call with both lists
4. Parse response: list of article IDs to auto-dismiss with reasons
5. Mark matched articles: `dismissed=1, auto_dismissed=1`
6. Log reasoning to fetch progress log

### LLM prompt

```
Here are articles the user has manually dismissed (they don't find these interesting):
{dismissed_titles}

Here are newly fetched articles:
{new_articles as id: title}

Based on the patterns in dismissed articles, identify which new articles the user
would likely dismiss too. Only dismiss articles that clearly match the patterns —
when in doubt, keep the article.

Return JSON:
{
  "dismiss": [{"id": <int>, "reason": "<brief reason>"}],
  "patterns_found": ["<pattern1>", "<pattern2>"]
}
```

### Database changes

- Add column: `articles.auto_dismissed BOOLEAN DEFAULT 0`
- Auto-dismissed articles have both `dismissed=1` AND `auto_dismissed=1`
- Manually dismissed articles have `dismissed=1, auto_dismissed=0`
- This lets the UI distinguish manual vs. auto in the dismissed view

### UI changes

- Show relevancy score on article cards (e.g., "Rel: 72%" label in meta row)
- In the dismissed view, auto-dismissed articles get an "Auto" badge
- Auto-dismissed articles can still be restored (which provides negative feedback for the classifier)

### Cost

~1 Haiku call per fetch, ~2K input tokens → ~$0.001/fetch. Negligible.

## Files to modify

- `app/scoring/classifier.py` — New file: the dismiss classifier
- `app/scheduler.py` — Add classify step after insert
- `app/database.py` — Add `auto_dismissed` column migration, add helper queries
- `app/templates/newspaper.html` — Show relevancy score in card, "Auto" badge in dismissed view

## Files unchanged

- `app/scoring/relevancy.py` — Scoring formula stays the same
- `app/scoring/feedback.py` — Star rating feedback stays the same
- `app/routes/dismiss.py` — Manual dismiss/restore endpoints stay the same

## Constraints

- Classifier runs post-insert so articles have IDs and summaries available
- Conservative by default: when in doubt, keep the article
- Restoring an auto-dismissed article should be treated the same as restoring a manual dismiss
