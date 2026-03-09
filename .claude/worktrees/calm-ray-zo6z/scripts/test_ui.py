"""
Playwright UI/UX verification tests for AI News Tracker.
Tests all 12 UI improvements implemented in the latest update.
Run: python3 scripts/test_ui.py
"""

import sys
import time
from playwright.sync_api import sync_playwright, expect

BASE = "http://localhost:8001"
PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
SKIP = "\033[33m~\033[0m"

results = []

def check(name, fn):
    try:
        fn()
        print(f"  {PASS} {name}")
        results.append((name, "pass", None))
    except Exception as e:
        msg = str(e).split("\n")[0][:120]
        print(f"  {FAIL} {name}")
        print(f"      {msg}")
        results.append((name, "fail", msg))

def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        # ── Load page ──────────────────────────────────────────────────────────
        print("\n[Setup] Loading page...")
        page.goto(BASE, wait_until="networkidle")
        has_articles = page.locator(".article-card").count() > 0
        print(f"  {'Articles present' if has_articles else 'No articles — some tests will be limited'}")

        # ── 1. Relevancy accent border ────────────────────────────────────────
        print("\n[1] Relevancy accent border")
        if has_articles:
            check("article-card has a relevancy class",
                  lambda: _assert(
                      lambda: page.locator(".article-card.relevancy-high, .article-card.relevancy-mid, .article-card.relevancy-low").count() > 0,
                      "No cards with relevancy-high/mid/low class"
                  ))
            check("card has visible border-left color",
                  lambda: _assert(
                      lambda: page.evaluate("""() => {
                          const card = document.querySelector('.article-card.relevancy-high, .article-card.relevancy-mid');
                          if (!card) return false;
                          const color = getComputedStyle(card).borderLeftColor;
                          return color && color !== 'rgba(0, 0, 0, 0)' && color !== 'transparent';
                      }"""),
                      "No visible border-left-color on relevancy card"
                  ))
            check("card title attribute contains 'Relevancy'",
                  lambda: _assert(
                      lambda: any("Relevancy" in (el.get_attribute("title") or "")
                                  for el in page.locator(".article-card").all()[:5]),
                      "No card with Relevancy tooltip"
                  ))
            check("score-bar-wrap is hidden",
                  lambda: _assert(
                      lambda: page.evaluate("""() => {
                          const el = document.querySelector('.score-bar-wrap');
                          if (!el) return true;
                          return getComputedStyle(el).display === 'none';
                      }"""),
                      "score-bar-wrap is still visible"
                  ))
        else:
            _skip("[1] No articles to test accent border")

        # ── 2. align-items: start on grid ─────────────────────────────────────
        print("\n[2] Grid align-items: start")
        check("newspaper-grid has align-items: start",
              lambda: _assert(
                  lambda: "start" in page.eval_on_selector(
                      ".newspaper-grid",
                      "el => getComputedStyle(el).alignItems"
                  ),
                  "align-items is not 'start'"
              ))

        # ── 3. Visited link colour ─────────────────────────────────────────────
        print("\n[3] Visited link colour")
        check(":visited color rule exists in stylesheet",
              lambda: _assert(
                  lambda: page.evaluate("""() => {
                      for (const sheet of document.styleSheets) {
                          try {
                              for (const rule of sheet.cssRules) {
                                  if (rule.selectorText && rule.selectorText.includes(':visited'))
                                      return true;
                              }
                          } catch {}
                      }
                      return false;
                  }"""),
                  "No :visited rule found in stylesheets"
              ))

        # ── 4. Card flexible height (min-height, no fixed height) ────────────
        print("\n[4] Card flexible height")
        if has_articles:
            check("card has min-height >= 200px",
                  lambda: _assert(
                      lambda: float(page.eval_on_selector(
                          ".article-card",
                          "el => parseFloat(getComputedStyle(el).minHeight)"
                      )) >= 200,
                      "Card min-height too small"
                  ))
            check("card has no fixed height (auto or 0)",
                  lambda: _assert(
                      lambda: page.evaluate("""() => {
                          const card = document.querySelector('.article-card');
                          const h = getComputedStyle(card).height;
                          // Should not be exactly 380px (old fixed height)
                          return parseFloat(h) !== 380;
                      }"""),
                      "Card still has fixed 380px height"
                  ))
        else:
            _skip("[4] No articles")

        # ── 5. Bookmark button ─────────────────────────────────────────────────
        print("\n[5] Bookmark button")
        if has_articles:
            check("bookmark-btn exists on cards",
                  lambda: page.locator(".bookmark-btn").first.wait_for(timeout=3000))
            check("clicking bookmark sets active class and localStorage",
                  lambda: _test_bookmark(page))
        else:
            _skip("[5] No articles")

        # ── 6. Undo dismiss toast ──────────────────────────────────────────────
        print("\n[6] Undo dismiss toast")
        if has_articles:
            check("undo-toast element exists (initially hidden)",
                  lambda: _assert(
                      lambda: page.locator("#undo-toast").count() == 1,
                      "#undo-toast not found"
                  ))
            check("dismissing a card shows the toast",
                  lambda: _test_dismiss_toast(page))
        else:
            _skip("[6] No articles")

        # ── 7. Dark mode toggle ────────────────────────────────────────────────
        print("\n[7] Dark mode")
        check("html.dark CSS rule exists in stylesheet",
              lambda: _assert(
                  lambda: page.evaluate("""() => {
                      for (const sheet of document.styleSheets) {
                          try {
                              for (const rule of sheet.cssRules) {
                                  if (rule.selectorText && rule.selectorText.includes('html.dark'))
                                      return true;
                              }
                          } catch {}
                      }
                      return false;
                  }"""),
                  "No html.dark CSS rule found"
              ))
        check("theme-toggle button exists",
              lambda: page.locator("#theme-toggle").wait_for(timeout=3000))
        check("clicking theme toggle adds .dark class to html",
              lambda: _test_theme_toggle(page))

        # ── 8. Sticky masthead ─────────────────────────────────────────────────
        print("\n[8] Sticky masthead")
        check("masthead has position: sticky",
              lambda: _assert(
                  lambda: page.eval_on_selector(
                      ".masthead",
                      "el => getComputedStyle(el).position"
                  ) == "sticky",
                  "Masthead is not sticky"
              ))

        # ── 9. Better pub-time tooltip ─────────────────────────────────────────
        print("\n[9] Pub-time tooltip")
        if has_articles:
            pub_els = page.locator(".pub-time[data-pub]").all()
            if pub_els:
                check("pub-time title is not raw UTC (contains locale-formatted date)",
                      lambda: _assert(
                          lambda: _check_tooltip(pub_els),
                          "Tooltip still looks like raw UTC string"
                      ))
            else:
                _skip("[9] No pub-time elements with data-pub")
        else:
            _skip("[9] No articles")

        # ── 10. Stars locked after rating ──────────────────────────────────────
        print("\n[10] Stars lock after rating")
        check("rated star-widget has pointer-events: none",
              lambda: _assert(
                  lambda: page.evaluate("""() => {
                      const sheet = [...document.styleSheets].find(s => {
                          try { return s.href && s.href.includes('style.css'); } catch { return false; }
                      });
                      if (!sheet) return false;
                      for (const rule of sheet.cssRules) {
                          if (rule.selectorText && rule.selectorText.includes('.star-widget.rated')
                              && rule.style && rule.style.pointerEvents === 'none')
                              return true;
                      }
                      return false;
                  }"""),
                  ".star-widget.rated pointer-events: none not found in CSS"
              ))

        # ── 11. Search input ──────────────────────────────────────────────────
        print("\n[11] Search input")
        check("card-search input exists",
              lambda: page.locator("#card-search").wait_for(timeout=3000))
        if has_articles:
            check("search filters cards by title",
                  lambda: _test_search(page))
        else:
            _skip("[11] No articles for search test")

        # ── Source interleaving ────────────────────────────────────────────────
        print("\n[+] Source interleaving on All Sources view")
        page.goto(BASE + "/?source=all", wait_until="networkidle")
        if page.locator(".article-card").count() >= 3:
            check("first 9 cards contain at least 2 distinct source types",
                  lambda: _assert(
                      lambda: _count_distinct_sources(page, 9) >= 2,
                      "First 9 cards all from same source — no interleaving"
                  ))
            check("no source appears in 3 consecutive cards",
                  lambda: _assert(
                      lambda: not _has_three_consecutive_same_source(page),
                      "A source appears 3+ times consecutively"
                  ))
        else:
            _skip("[+] Not enough articles to test interleaving")
        # Restore all-sources page for subsequent tests
        page.goto(BASE, wait_until="networkidle")

        # ── Last-fetched local time ────────────────────────────────────────────
        print("\n[+] Last-fetched time in browser local time")
        check("#last-fetched span is populated by JS",
              lambda: _assert(
                  lambda: len(page.locator("#last-fetched").inner_text().strip()) > 0,
                  "#last-fetched is empty"
              ))
        check("#last-fetched does not contain raw UTC format (YYYY-MM-DD HH:MM:SS)",
              lambda: _assert(
                  lambda: not _looks_like_raw_utc(page.locator("#last-fetched").inner_text()),
                  "Text still looks like raw UTC"
              ))

        # ── 12. Keyboard navigation ────────────────────────────────────────────
        print("\n[12] Keyboard navigation")
        check("kbd-hint element exists",
              lambda: page.locator("#kbd-hint").wait_for(timeout=3000))
        if has_articles:
            check("pressing 'j' focuses first card (kb-focus class)",
                  lambda: _test_keyboard_nav(page))
        else:
            _skip("[12] No articles for keyboard nav test")

        browser.close()

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    passed = sum(1 for _, s, _ in results if s == "pass")
    failed = sum(1 for _, s, _ in results if s == "fail")
    skipped = sum(1 for _, s, _ in results if s == "skip")
    total = len(results)
    print(f"Results: {passed}/{total} passed  |  {failed} failed  |  {skipped} skipped")
    if failed:
        print("\nFailed tests:")
        for name, status, msg in results:
            if status == "fail":
                print(f"  {FAIL} {name}: {msg}")
    print()
    return failed == 0


# ── Helpers ────────────────────────────────────────────────────────────────────

def _assert(condition_fn, message):
    if not condition_fn():
        raise AssertionError(message)

def _skip(label):
    print(f"  {SKIP} {label} (skipped — no data)")
    results.append((label, "skip", None))

def _count_distinct_sources(page, n):
    cards = page.locator(".article-card").all()[:n]
    sources = set()
    for card in cards:
        cls = card.get_attribute("class") or ""
        for s in ("src-youtube", "src-reddit", "src-hackernews"):
            if s in cls:
                sources.add(s)
    return len(sources)

def _has_three_consecutive_same_source(page):
    cards = page.locator(".article-card").all()
    sources = []
    for card in cards:
        cls = card.get_attribute("class") or ""
        for s in ("src-youtube", "src-youtube_channel", "src-reddit", "src-hackernews"):
            if s in cls:
                sources.append(s)
                break
    for i in range(len(sources) - 2):
        if sources[i] == sources[i+1] == sources[i+2]:
            return True
    return False

def _looks_like_raw_utc(text):
    """Return True if text matches 'YYYY-MM-DD HH:MM' raw UTC pattern."""
    import re
    return bool(re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', text))

def _check_tooltip(pub_els):
    for el in pub_els:
        title = el.get_attribute("title") or ""
        # Raw UTC looks like "2026-02-25 14:30:00" — locale formatted won't have that pattern
        if title and not (len(title) == 19 and title[4] == "-" and title[7] == "-"):
            return True
    return False

def _test_bookmark(page):
    btn = page.locator(".bookmark-btn").first
    card = page.locator(".article-card").first
    article_id = card.get_attribute("data-article-id")

    btn.click()
    page.wait_for_timeout(300)

    # Check active class
    has_active = "active" in (btn.get_attribute("class") or "")
    # Check localStorage
    stored = page.evaluate(f"""() => {{
        const raw = localStorage.getItem('ai-news-bookmarks');
        const arr = JSON.parse(raw || '[]');
        return arr.includes('{article_id}');
    }}""")
    if not has_active:
        raise AssertionError("bookmark-btn does not have 'active' class after click")
    if not stored:
        raise AssertionError("article ID not found in localStorage after bookmark")

    # Undo bookmark
    btn.click()

def _test_dismiss_toast(page):
    # Reload to get a fresh card
    page.reload(wait_until="networkidle")
    dismiss_btn = page.locator(".dismiss-btn").first
    dismiss_btn.click()
    page.wait_for_timeout(400)
    visible = page.eval_on_selector("#undo-toast", "el => el.classList.contains('visible')")
    if not visible:
        raise AssertionError("Toast did not become visible after dismiss")

def _test_keyboard_nav(page):
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(300)
    # Focus body first
    page.keyboard.press("Tab")
    page.wait_for_timeout(100)
    # Press 'j' to focus first card
    page.keyboard.press("j")
    page.wait_for_timeout(300)
    focused = page.locator(".article-card.kb-focus").count()
    if focused == 0:
        raise AssertionError("No card has kb-focus class after pressing 'j'")


def _test_theme_toggle(page):
    # Click the theme toggle button
    page.locator("#theme-toggle").click()
    page.wait_for_timeout(300)
    is_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
    if not is_dark:
        raise AssertionError("html element does not have 'dark' class after theme toggle click")
    # Background should differ from light mode cream
    bg = page.eval_on_selector("body", "el => getComputedStyle(el).backgroundColor")
    if bg == "rgb(245, 240, 232)":
        raise AssertionError("Background unchanged from light mode after dark toggle")
    # Toggle back to light
    page.locator("#theme-toggle").click()
    page.wait_for_timeout(200)

def _test_search(page):
    page.reload(wait_until="networkidle")
    total_before = page.locator(".article-card").count()
    if total_before == 0:
        raise AssertionError("No cards to test search")
    # Type a query that likely won't match all cards
    page.fill("#card-search", "xyznonexistent12345")
    page.wait_for_timeout(300)
    visible = page.evaluate("""() => {
        return [...document.querySelectorAll('.article-card')].filter(
            c => getComputedStyle(c).display !== 'none'
        ).length;
    }""")
    if visible >= total_before:
        raise AssertionError("Search did not hide any cards for nonsense query")
    # Clear search
    page.fill("#card-search", "")
    page.wait_for_timeout(200)


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
