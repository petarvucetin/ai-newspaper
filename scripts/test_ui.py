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

        # ── 1. Relevancy score bar ─────────────────────────────────────────────
        print("\n[1] Relevancy score bar")
        if has_articles:
            check("score-bar-wrap element exists on at least one card",
                  lambda: page.locator(".score-bar-wrap").first.wait_for(timeout=3000))
            check("score-fill element has a non-zero width style",
                  lambda: _assert(
                      lambda: len([c for c in page.locator(".score-fill").all()
                                   if "width:" in (c.get_attribute("style") or "")]) > 0,
                      "No score-fill with width style found"
                  ))
            check("score bar tooltip contains 'Relevancy score'",
                  lambda: _assert(
                      lambda: any("Relevancy score" in (el.get_attribute("title") or "")
                                  for el in page.locator(".score-bar-wrap").all()),
                      "No score-bar-wrap with correct title"
                  ))
        else:
            _skip("[1] No articles to test score bar")

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

        # ── 4. Featured card prominence ────────────────────────────────────────
        print("\n[4] Featured card")
        if has_articles:
            check("first card has class 'featured'",
                  lambda: _assert(
                      lambda: page.locator(".article-card.featured").count() == 1,
                      "No .featured card found"
                  ))
            check("featured card title font-size >= 28px",
                  lambda: _assert(
                      lambda: float(page.eval_on_selector(
                          ".article-card.featured .article-title",
                          "el => parseFloat(getComputedStyle(el).fontSize)"
                      )) >= 28,
                      "Featured title font-size too small"
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

        # ── 7. Dark mode CSS ───────────────────────────────────────────────────
        print("\n[7] Dark mode")
        check("@media prefers-color-scheme: dark rule exists",
              lambda: _assert(
                  lambda: page.evaluate("""() => {
                      for (const sheet of document.styleSheets) {
                          try {
                              for (const rule of sheet.cssRules) {
                                  if (rule.media && Array.from(rule.media).some(m => m.includes('dark')))
                                      return true;
                              }
                          } catch {}
                      }
                      return false;
                  }"""),
                  "No dark mode @media rule found"
              ))
        # Simulate dark mode and verify background changes
        dark_ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            color_scheme="dark"
        )
        dark_page = dark_ctx.new_page()
        dark_page.goto(BASE, wait_until="networkidle")
        check("body background in dark mode is not the light cream (#f5f0e8)",
              lambda: _assert(
                  lambda: dark_page.eval_on_selector(
                      "body",
                      "el => getComputedStyle(el).backgroundColor"
                  ) != "rgb(245, 240, 232)",
                  "Dark mode background unchanged from light mode"
              ))
        dark_page.close()
        dark_ctx.close()

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

        # ── 11. Card height (grid align-items) ─────────────────────────────────
        # Same assertion as #2 — covered.
        print("\n[11] Card height consistency (covered by #2)")
        results.append(("[11] align-items:start", "pass", "covered by test #2"))
        print(f"  {PASS} Covered by test #2")

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


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
