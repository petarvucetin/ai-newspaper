# UI/UX Redesign — "Modern Reader" Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Evolve the newspaper-style AI news tracker into a polished modern reader with adaptive cards, thumbnails, refined interactions, and intentional dark mode — without changing the backend or database.

**Architecture:** Pure CSS + vanilla JS + Jinja2 template changes. One small backend addition: pass source counts to the template for filter pill badges. The `thumbnail_url` column already exists in the DB and is already returned by queries via `a.*` — we just need to render it.

**Tech Stack:** CSS custom properties, CSS Grid, vanilla JS, Jinja2 macros, FastAPI/Jinja2 templates.

**Design doc:** `docs/plans/2026-03-02-ui-ux-redesign-design.md`

---

### Task 1: Card Grid — Remove Fixed Heights and Improve Grid Spacing

**Files:**
- Modify: `app/static/style.css:260-278` (`.newspaper-grid` and `.article-card`)

**Step 1: Update the grid layout**

Replace the current grid and card rules:

```css
/* ---- Newspaper Grid ---- */
.newspaper-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding: 0;
  align-items: start;
}

/* Standard card */
.article-card {
  background: var(--cream);
  padding: 0;  /* padding moves inside .article-body */
  display: flex;
  flex-direction: column;
  min-height: 200px;
  overflow: hidden;
  border-radius: 6px;
  border: 1px solid var(--rule);
  transition: box-shadow 0.2s, transform 0.2s;
}

.article-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}
```

Also update `.article-body` to add internal padding:

```css
.article-body {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  flex: 1;
  overflow: hidden;
  padding: 0.8rem 1rem;
}
```

**Step 2: Update responsive breakpoints**

The responsive rules at the bottom of `style.css:924-934` stay as-is (2-col at 900px, 1-col at 600px).

**Step 3: Verify visually**

Run the app (`python -m app.main` or equivalent), open the newspaper page, and confirm:
- Cards no longer have fixed 380px height
- Cards grow to fit content
- 12px gaps between cards
- Subtle border on each card
- Hover shows shadow lift

**Step 4: Commit**

```bash
git add app/static/style.css
git commit -m "style: replace fixed card height with flexible min-height and 12px grid gaps"
```

---

### Task 2: Left Accent Border (Replaces Score Bar)

**Files:**
- Modify: `app/static/style.css` — add `.relevancy-accent` rule, remove/hide `.score-bar-wrap`
- Modify: `app/templates/newspaper.html:43-108` — update `article_card` macro

**Step 1: Add accent border CSS**

Add after the `.article-card:hover` rule:

```css
/* ---- Relevancy accent border ---- */
.article-card {
  border-left: 3px solid transparent;
}
.article-card.relevancy-high {
  border-left-color: var(--score-high);
}
.article-card.relevancy-mid {
  border-left-color: var(--score-mid);
}
.article-card.relevancy-low {
  border-left-color: var(--score-low);
}
```

**Step 2: Hide the inline score bar**

In `style.css`, add:
```css
.score-bar-wrap { display: none; }
```

**Step 3: Update the article_card macro**

In `newspaper.html`, update the `<article>` opening tag (line 44) to include a relevancy class:

```jinja2
{% macro article_card(article, is_old, active_filter) %}
  {%- set rscore = article.relevancy_score or 0 -%}
  {%- if rscore >= 0.7 -%}{%- set rel_cls = 'relevancy-high' -%}
  {%- elif rscore >= 0.4 -%}{%- set rel_cls = 'relevancy-mid' -%}
  {%- else -%}{%- set rel_cls = 'relevancy-low' -%}
  {%- endif -%}
  <article class="article-card src-{{ article.source_type }} {{ rel_cls }}{% if is_old %} collapsed{% endif %}"
           data-article-id="{{ article.id }}"
           data-source-id="{{ article.source_id }}"
           data-source-name="{{ article.source_name }}"
           title="Relevancy: {{ '%.0f'|format(rscore * 100) }}%">
```

Remove the `{{ score_bar(article.relevancy_score) }}` call from inside `article-scroll` (line 73-74).

**Step 4: Verify visually**

Confirm cards show colored left borders based on relevancy and the inline score bar is gone. Hovering a card shows the relevancy percentage in the tooltip.

**Step 5: Commit**

```bash
git add app/static/style.css app/templates/newspaper.html
git commit -m "style: replace inline score bar with left accent border colored by relevancy"
```

---

### Task 3: YouTube Thumbnail Headers

**Files:**
- Modify: `app/templates/newspaper.html` — add thumbnail rendering to `article_card` macro
- Modify: `app/static/style.css` — add `.article-thumb` styles

**Step 1: Add thumbnail CSS**

```css
/* ---- Thumbnail header (YouTube) ---- */
.article-thumb {
  width: 100%;
  aspect-ratio: 16 / 9;
  max-height: 160px;
  object-fit: cover;
  display: block;
  border-bottom: 1px solid var(--rule);
}
```

**Step 2: Add thumbnail to card macro**

In `newspaper.html`, inside the `article_card` macro, add the thumbnail **before** `<div class="article-body">` (before line 48):

```jinja2
    {% if article.source_type in ('youtube', 'youtube_channel') and article.thumbnail_url %}
    <img class="article-thumb" src="{{ article.thumbnail_url }}" alt="" loading="lazy">
    {% endif %}
```

**Step 3: Add dark mode thumbnail treatment**

In the dark mode section of `style.css`:
```css
.article-thumb {
  opacity: 0.9;
  border-bottom-color: var(--rule);
}
```

**Step 4: Verify visually**

Open the app, check YouTube articles show thumbnails at the top of cards. Reddit/HN cards should not show any image.

**Step 5: Commit**

```bash
git add app/static/style.css app/templates/newspaper.html
git commit -m "feat: show YouTube thumbnails at top of article cards"
```

---

### Task 4: Card Anatomy — Reorganize Internal Layout

**Files:**
- Modify: `app/templates/newspaper.html:43-108` — restructure `article_card` macro
- Modify: `app/static/style.css` — update `.article-meta-top`, `.article-footer`, `.article-scroll`

**Step 1: Rewrite the card macro body**

Replace the `<div class="article-body">` content (lines 48-106) with the new structure:

```jinja2
    <div class="article-body">
      <div class="article-meta-top">
        {{ source_badge(article.source_type, article.source_name) }}
        {% if article.published_at %}
        <span class="pub-time" data-pub="{{ article.published_at }}" data-iso="{{ article.published_at }}">{{ article.published_at[:16] }}</span>
        {% endif %}
        {% if is_old %}
        <button class="expand-toggle" title="Expand article">&#9660;</button>
        {% endif %}
      </div>

      <div class="article-metrics">
        {% if article.source_type in ('youtube', 'youtube_channel') %}
          {% if article.upvotes > 0 %}
          <span class="view-count">&#128065; {{ fmt_count(article.upvotes) }} views</span>
          {% endif %}
        {% else %}
          {% if article.upvotes > 0 %}
          <span class="upvotes">&#9650; {{ fmt_count(article.upvotes) }}</span>
          {% endif %}
          {% if article.source_type == 'reddit' and article.num_comments %}
          <span class="comment-count">&#128172; {{ fmt_count(article.num_comments) }}</span>
          {% endif %}
        {% endif %}
      </div>

      <div class="article-scroll">
        <h2 class="article-title">
          <a href="{{ article.url }}" target="_blank" rel="noopener">{{ article.title }}</a>
        </h2>

        {% if article.summary %}
        <div class="article-summary">
          {% for para in article.summary.split('\n\n') %}
            {% if para.strip() %}<p>{{ para.strip() }}</p>{% endif %}
          {% endfor %}
        </div>
        {% endif %}
      </div>

      <div class="article-footer">
        <div class="article-actions">
          {{ star_widget(article.id, article.user_rating) }}
          <button class="bookmark-btn" data-article-id="{{ article.id }}" title="Bookmark">&#9711;</button>
          {% if active_filter == 'dismissed' %}
          <button class="restore-btn" data-article-id="{{ article.id }}" title="Restore article">&#8617;</button>
          {% else %}
          <button class="dismiss-btn" data-article-id="{{ article.id }}" title="Dismiss article">&#10005;</button>
          {% endif %}
          {% if article.source_type in ('reddit', 'youtube_channel', 'youtube') %}
          <button class="remove-source-btn" title="Remove source: {{ article.source_name }}">&#128683;</button>
          {% endif %}
        </div>
        {% if article.author %}<span class="article-author-hint" title="{{ article.author }}">{{ article.author }}</span>{% endif %}
      </div>
    </div>
```

**Step 2: Add CSS for `.article-metrics` and `.article-author-hint`**

```css
.article-metrics {
  display: flex;
  gap: 0.6rem;
  font-family: var(--font-sans);
  font-size: 0.72rem;
  color: var(--ink-muted);
}

.article-author-hint {
  font-family: var(--font-sans);
  font-size: 0.65rem;
  color: var(--ink-muted);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

**Step 3: Remove the old `.article-byline` CSS** (it was used to display the author in the footer).

**Step 4: Verify visually**

Confirm the new card layout: source badge + time on one row, metrics on a separate row, then title, summary, and actions.

**Step 5: Commit**

```bash
git add app/static/style.css app/templates/newspaper.html
git commit -m "refactor: reorganize card anatomy with separate metrics row and compact author"
```

---

### Task 5: Masthead — Glassmorphism and Settings Dropdown

**Files:**
- Modify: `app/templates/base.html:11-36` — restructure masthead
- Modify: `app/static/style.css:68-170` — masthead styles

**Step 1: Update masthead HTML in `base.html`**

Replace the masthead (lines 11-36) with:

```html
  <header class="masthead">
    <div class="masthead-inner">
      <div class="masthead-meta">
        <span class="edition">Daily Edition &mdash; <span id="last-fetched"
          {% if last_fetched_utc is defined and last_fetched_utc %}data-utc="{{ last_fetched_utc }}"{% endif %}
        ></span></span>
      </div>
      <h1 class="paper-title">The AI Intelligence</h1>
      <div class="masthead-links">
        <a href="/admin">Admin</a>
        <button id="theme-toggle" class="theme-toggle-btn" title="Toggle dark/light mode" aria-label="Toggle theme">
          <span class="theme-icon">&#9790;</span>
        </button>
        <div class="settings-dropdown">
          <button class="settings-btn" title="Settings" aria-label="Settings">&#9881;</button>
          <div class="settings-panel">
            <div class="font-size-ctrl">
              <span class="settings-label">Font size</span>
              <button id="font-dec" title="Decrease font size">A&minus;</button>
              <button id="font-inc" title="Increase font size">A+</button>
            </div>
            <span class="version-tag">v{{ app_version }}</span>
          </div>
        </div>
      </div>
    </div>
    <nav class="filter-nav">
      {% block filter_nav %}{% endblock %}
    </nav>
  </header>
```

**Step 2: Update masthead CSS**

```css
.masthead {
  background: color-mix(in srgb, var(--cream) 85%, transparent);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-bottom: 3px double var(--ink);
  padding: 0.75rem 1.5rem 0;
  position: sticky;
  top: 0;
  z-index: 100;
}

/* Theme toggle */
.theme-toggle-btn {
  background: none;
  border: 1px solid var(--rule);
  border-radius: 50%;
  width: 28px;
  height: 28px;
  cursor: pointer;
  color: var(--ink-light);
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
}
.theme-toggle-btn:hover {
  background: var(--ink);
  color: var(--cream);
}

/* Settings dropdown */
.settings-dropdown {
  position: relative;
}
.settings-btn {
  background: none;
  border: 1px solid var(--rule);
  border-radius: 50%;
  width: 28px;
  height: 28px;
  cursor: pointer;
  color: var(--ink-light);
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.settings-btn:hover { background: var(--cream-dark); }
.settings-panel {
  display: none;
  position: absolute;
  right: 0;
  top: 110%;
  background: var(--cream);
  border: 1px solid var(--rule);
  border-radius: 6px;
  padding: 0.6rem 0.8rem;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  z-index: 200;
  min-width: 140px;
}
.settings-dropdown.open .settings-panel { display: block; }
.settings-label {
  font-family: var(--font-sans);
  font-size: 0.75rem;
  color: var(--ink-muted);
  margin-right: 0.4rem;
}

.masthead-links {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
```

**Step 3: Add settings dropdown toggle JS in `base.html`**

Add to the `<script>` block:
```js
// ---- Settings dropdown ----
const settingsDropdown = document.querySelector('.settings-dropdown');
if (settingsDropdown) {
  const settingsBtn = settingsDropdown.querySelector('.settings-btn');
  settingsBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    settingsDropdown.classList.toggle('open');
  });
  document.addEventListener('click', () => settingsDropdown.classList.remove('open'));
}
```

**Step 4: Verify visually**

- Masthead should have a frosted-glass look when scrolling
- Gear icon opens a dropdown with font size controls
- Moon icon visible (functionality added in Task 8)

**Step 5: Commit**

```bash
git add app/templates/base.html app/static/style.css
git commit -m "style: masthead glassmorphism, settings dropdown, theme toggle button"
```

---

### Task 6: Filter Nav — Segmented Control Pills with Counts

**Files:**
- Modify: `app/templates/newspaper.html` — move filter nav into `filter_nav` block with pill styling and counts
- Modify: `app/routes/newspaper.py` — pass `source_counts` dict to template
- Modify: `app/static/style.css` — restyle `.filter-btn` as pills

**Step 1: Add source counts to the route**

In `app/routes/newspaper.py`, add a helper and update the `newspaper` function:

```python
def _source_counts() -> dict[str, int]:
    """Count non-dismissed articles per source type."""
    with db_conn() as con:
        rows = con.execute(
            "SELECT s.source_type, COUNT(*) as cnt "
            "FROM articles a JOIN sources s ON a.source_id = s.id "
            "WHERE COALESCE(a.dismissed, 0) = 0 "
            "GROUP BY s.source_type"
        ).fetchall()
    counts = {r["source_type"]: r["cnt"] for r in rows}
    # Merge youtube + youtube_channel
    yt = counts.pop("youtube", 0) + counts.pop("youtube_channel", 0)
    if yt:
        counts["youtube"] = yt
    return counts
```

Add `source_counts=_source_counts()` to the template context dict.

**Step 2: Override the `filter_nav` block in `newspaper.html`**

Remove the hardcoded filter nav from `base.html` and define it in `newspaper.html`:

```jinja2
{% block filter_nav %}
  <a href="/?source=all" class="filter-btn {% if active_filter == 'all' %}active{% endif %}">All</a>
  <a href="/?source=reddit" class="filter-btn {% if active_filter == 'reddit' %}active{% endif %}">Reddit {% if source_counts.get('reddit') %}<span class="filter-count">{{ source_counts.reddit }}</span>{% endif %}</a>
  <a href="/?source=youtube" class="filter-btn {% if active_filter == 'youtube' %}active{% endif %}">YouTube {% if source_counts.get('youtube') %}<span class="filter-count">{{ source_counts.youtube }}</span>{% endif %}</a>
  <a href="/?source=hackernews" class="filter-btn {% if active_filter == 'hackernews' %}active{% endif %}">Hacker News {% if source_counts.get('hackernews') %}<span class="filter-count">{{ source_counts.hackernews }}</span>{% endif %}</a>
  <a href="/?source=bookmarks" class="filter-btn {% if active_filter == 'bookmarks' %}active{% endif %}">Bookmarks</a>
  <a href="/?source=dismissed" class="filter-btn {% if active_filter == 'dismissed' %}active{% endif %}">Dismissed</a>
  <input type="search" id="card-search" class="card-search" placeholder="Search articles..." autocomplete="off">
{% endblock %}
```

**Step 3: Restyle filter nav CSS**

```css
.filter-nav {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.4rem 0;
  flex-wrap: wrap;
}

.filter-btn {
  font-family: var(--font-sans);
  font-size: 0.78rem;
  padding: 0.3rem 0.75rem;
  text-decoration: none;
  color: var(--ink-light);
  border: 1px solid transparent;
  border-radius: 999px;
  transition: background 0.15s, border-color 0.15s;
}
.filter-btn:hover { background: var(--cream-dark); border-color: var(--rule); }
.filter-btn.active {
  background: var(--ink);
  color: var(--cream);
  font-weight: 600;
}

.filter-count {
  font-size: 0.65rem;
  font-weight: 600;
  opacity: 0.7;
  margin-left: 0.15rem;
}

/* Search input */
.card-search {
  margin-left: auto;
  padding: 0.3rem 0.7rem;
  border: 1px solid var(--rule);
  border-radius: 999px;
  background: var(--cream);
  font-family: var(--font-sans);
  font-size: 0.78rem;
  color: var(--ink);
  width: 180px;
  transition: width 0.2s, border-color 0.2s;
}
.card-search:focus {
  outline: none;
  border-color: var(--accent);
  width: 240px;
}
```

**Step 4: Add client-side search JS in `newspaper.html`**

Add to the bottom of the scripts block:

```js
// ---- Client-side search ----
const searchInput = document.getElementById('card-search');
if (searchInput) {
  searchInput.addEventListener('input', () => {
    const q = searchInput.value.toLowerCase().trim();
    document.querySelectorAll('.article-card').forEach(card => {
      if (!q) { card.style.removeProperty('display'); return; }
      const title = card.querySelector('.article-title')?.textContent.toLowerCase() || '';
      const summary = card.querySelector('.article-summary')?.textContent.toLowerCase() || '';
      card.style.display = (title.includes(q) || summary.includes(q)) ? '' : 'none';
    });
  });
}
```

**Step 5: Commit**

```bash
git add app/static/style.css app/templates/base.html app/templates/newspaper.html app/routes/newspaper.py
git commit -m "feat: segmented filter pills with source counts and client-side search"
```

---

### Task 7: Dismiss Animation & Undo Toast Progress Bar

**Files:**
- Modify: `app/static/style.css` — add slide-left dismiss animation, toast progress bar
- Modify: `app/templates/newspaper.html` — update toast HTML and dismiss JS

**Step 1: Add dismiss slide-left animation CSS**

```css
/* ---- Dismiss slide-out ---- */
.article-card.dismissing {
  transition: opacity 0.25s, transform 0.25s;
  opacity: 0;
  transform: translateX(-30px);
}
```

**Step 2: Update undo toast HTML and CSS**

In `newspaper.html`, replace the undo toast div:

```html
<div id="undo-toast">
  <span>Article dismissed</span>
  <button id="undo-btn">Undo</button>
  <div class="toast-progress"><div class="toast-progress-bar"></div></div>
</div>
```

Add CSS:
```css
.toast-progress {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: rgba(255,255,255,0.15);
  border-radius: 0 0 4px 4px;
  overflow: hidden;
}
.toast-progress-bar {
  height: 100%;
  background: var(--cream);
  width: 100%;
  transform-origin: left;
  transition: transform 4s linear;
}
#undo-toast.visible .toast-progress-bar {
  transform: scaleX(0);
}
```

Also add `position: relative;` to `#undo-toast`.

**Step 3: Update dismiss JS**

Replace the card removal in the `dismissCard` function to use the new class:

```js
card.classList.add('dismissing');
setTimeout(() => card.remove(), 250);
```

**Step 4: Add bookmark bounce animation**

```css
@keyframes bookmark-bounce {
  0% { transform: scale(1); }
  40% { transform: scale(1.3); }
  100% { transform: scale(1); }
}
.bookmark-btn.bouncing {
  animation: bookmark-bounce 0.25s ease;
}
```

In the bookmark click handler, add:
```js
btn.classList.add('bouncing');
setTimeout(() => btn.classList.remove('bouncing'), 250);
```

**Step 5: Commit**

```bash
git add app/static/style.css app/templates/newspaper.html
git commit -m "style: slide-left dismiss animation, toast progress bar, bookmark bounce"
```

---

### Task 8: Dark Mode Toggle

**Files:**
- Modify: `app/templates/base.html` — add dark mode toggle logic
- Modify: `app/static/style.css` — refine dark palette, add `.dark` class support

**Step 1: Change dark mode from media query to class-based**

Replace the `@media (prefers-color-scheme: dark)` block with a `.dark` class on `<html>`:

```css
html.dark {
  --cream: #141210;
  --cream-dark: #1e1b17;
  --ink: #ddd5c4;
  --ink-light: #b8b0a0;
  --ink-muted: #7a7060;
  --rule: #2e2a22;
  --accent: #d4736a;
  --star-off: #4a4535;
  --star-on: #c9a227;
  --score-low: #4a4535;
  --score-mid: #c9a227;
  --score-high: #3a9a3a;
}

html.dark .fetch-log { background: #0e0d0b; }
html.dark .admin-msg { background: #1a3a26; color: #7acc99; }
html.dark .cookies-alert-ok    { background: #1a3a26; color: #7acc99; }
html.dark .cookies-alert-warn  { background: #3a3010; color: #d4a040; }
html.dark .cookies-alert-danger{ background: #3a1010; color: #d47070; }
html.dark .badge-running { background: #3a3010; color: #d4a040; }
html.dark .badge-done    { background: #1a3a26; color: #7acc99; }
html.dark .badge-error   { background: #3a1010; color: #d47070; }
html.dark .status-pill.pinned     { background: #1a5a2a; }
html.dark .status-pill.discovered { background: #5a4a00; }
html.dark .btn-accent { background: #1a5a2a; border-color: #1a5a2a; }
html.dark .btn-danger { background: #6b1a1a; border-color: #6b1a1a; }
html.dark .article-card {
  background: var(--cream-dark);
}
html.dark .article-thumb {
  opacity: 0.85;
}
html.dark .card-search {
  background: var(--cream-dark);
}
```

**Step 2: Add theme toggle JS in `base.html`**

```js
// ---- Theme toggle ----
const THEME_KEY = 'ai-news-theme';
const themeToggle = document.getElementById('theme-toggle');
const themeIcon = themeToggle?.querySelector('.theme-icon');

function applyTheme(mode) {
  if (mode === 'dark') {
    document.documentElement.classList.add('dark');
    if (themeIcon) themeIcon.textContent = '\u2600'; // sun
  } else {
    document.documentElement.classList.remove('dark');
    if (themeIcon) themeIcon.textContent = '\u263E'; // moon
  }
}

// Init: check localStorage, then system preference
(function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved) {
    applyTheme(saved);
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    applyTheme('dark');
  }
})();

if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const isDark = document.documentElement.classList.contains('dark');
    const next = isDark ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem(THEME_KEY, next);
  });
}
```

**Step 3: Verify**

- Click the moon/sun icon — theme toggles
- Refresh — theme persists
- Cards in dark mode have slightly lighter background than the page

**Step 4: Commit**

```bash
git add app/static/style.css app/templates/base.html
git commit -m "feat: manual dark mode toggle with refined dark palette"
```

---

### Task 9: Keyboard Nav Refinement & Tab Crossfade

**Files:**
- Modify: `app/static/style.css` — update `.kb-focus`, add tab crossfade
- Modify: `app/templates/newspaper.html` — update tab switching JS

**Step 1: Replace harsh outline with accent underline**

```css
.article-card.kb-focus {
  outline: none;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08), inset 0 -3px 0 var(--accent);
}
```

**Step 2: Add tab crossfade CSS**

```css
.tab-panel {
  display: none;
  opacity: 0;
  transition: opacity 0.2s;
}
.tab-panel.active {
  display: block;
  opacity: 1;
}
```

Note: CSS transitions don't work across `display: none/block` changes. Use a class-based approach with `visibility` or use JS to add the class after a frame. Simplest approach — use JS:

**Step 3: Update tab switching JS**

Replace the tab click handler:

```js
document.querySelectorAll('.page-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.page-tab').forEach(t => t.classList.remove('active'));
    const panels = document.querySelectorAll('.tab-panel');
    // Fade out current
    panels.forEach(p => { p.style.opacity = '0'; });
    setTimeout(() => {
      panels.forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const target = document.getElementById('tab-' + tab.dataset.tab);
      target.classList.add('active');
      // Trigger reflow then fade in
      requestAnimationFrame(() => { target.style.opacity = '1'; });
    }, 150);
  });
});
```

**Step 4: Commit**

```bash
git add app/static/style.css app/templates/newspaper.html
git commit -m "style: keyboard nav accent underline, tab crossfade transition"
```

---

### Task 10: Empty States & Footer Polish

**Files:**
- Modify: `app/templates/newspaper.html` — update empty state HTML
- Modify: `app/templates/base.html` — simplify footer
- Modify: `app/static/style.css` — empty state and footer refinements

**Step 1: Add SVG newspaper illustration to empty state**

In `newspaper.html`, update the empty state blocks:

```html
<div class="empty-state">
  <svg class="empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M4 22h16a2 2 0 002-2V4a2 2 0 00-2-2H8a2 2 0 00-2 2v16a2 2 0 01-2 2zm0 0a2 2 0 01-2-2v-9c0-1.1.9-2 2-2h2"/>
    <line x1="10" y1="6" x2="18" y2="6"/>
    <line x1="10" y1="10" x2="18" y2="10"/>
    <line x1="10" y1="14" x2="14" y2="14"/>
  </svg>
  <h2>No articles yet</h2>
  <p>The daily fetch hasn't run yet. Visit <a href="/admin">Admin</a> to trigger a manual fetch.</p>
</div>
```

**Step 2: Add empty icon CSS**

```css
.empty-icon {
  color: var(--ink-muted);
  margin-bottom: 1rem;
  opacity: 0.5;
}
```

**Step 3: Simplify footer in `base.html`**

```html
  <footer class="footer">
    AI News Tracker &mdash; Daily AI digest
  </footer>
```

**Step 4: Commit**

```bash
git add app/static/style.css app/templates/newspaper.html app/templates/base.html
git commit -m "style: SVG empty state illustration, simplified footer"
```

---

### Task 11: Update Playwright Tests

**Files:**
- Modify: `scripts/test_ui.py` — update tests to match new UI structure

**Step 1: Review existing tests**

Read `scripts/test_ui.py` fully. The tests check:
- Score bar existence (will need removal — replaced by accent border)
- Card height consistency (will need update — no longer fixed 380px)
- Grid alignment, bookmark, dismiss, keyboard nav, dark mode, etc.

**Step 2: Update tests**

- Replace score bar test with accent border test (check `border-left-color` on `.article-card`)
- Replace card height test with min-height test (`min-height: 200px`, no fixed height)
- Update dark mode test to use `.dark` class instead of `prefers-color-scheme`
- Add a test for the theme toggle button
- Add a test for the search input functionality
- Update any selectors that changed (e.g., `.article-byline` → `.article-author-hint`)

**Step 3: Run the tests**

```bash
python scripts/test_ui.py
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add scripts/test_ui.py
git commit -m "test: update Playwright tests for new UI structure"
```

---

### Task 12: Final Visual Audit & Cleanup

**Step 1: Remove any dead CSS**

Search `style.css` for rules that no longer have matching HTML:
- `.score-bar-wrap` — display: none is fine, or remove entirely
- `.article-byline` — removed in favor of `.article-author-hint`
- Any other orphaned rules

**Step 2: Test all functionality end-to-end**

Manually verify:
- [ ] Star ratings still work (click, lock, persist)
- [ ] Bookmarks work (add, remove, filter view, localStorage persistence)
- [ ] Dismiss + undo works (slide animation, progress bar, undo button)
- [ ] Keyboard nav works (j/k/d/b/Enter/?)
- [ ] Font size control works (from settings dropdown)
- [ ] Dark mode toggle works (persists across refresh)
- [ ] Source filter pills work (with counts)
- [ ] Search filters articles in real-time
- [ ] Fresh/Archive tabs switch with crossfade
- [ ] YouTube cards show thumbnails
- [ ] Responsive: 2-col at 900px, 1-col at 600px
- [ ] Admin page still works (out of scope but should not be broken)

**Step 3: Commit final cleanup**

```bash
git add -A
git commit -m "chore: remove dead CSS, final UI/UX redesign cleanup"
```
