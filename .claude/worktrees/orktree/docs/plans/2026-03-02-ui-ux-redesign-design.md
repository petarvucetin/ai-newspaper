# UI/UX Redesign — "Modern Reader"

**Date:** 2026-03-02
**Approach:** Evolve newspaper theme into a refined modern reader while keeping serif character.
**Scope:** CSS, templates, and client-side JS only. No backend/database changes needed.

---

## 1. Adaptive Card Grid

- Replace fixed `height: 380px` with `min-height: 200px` and no max-height. Cards grow to fit content.
- Change grid gap from 1px solid rule to 12px gutters with visible card backgrounds (subtle border or shadow).
- Use `grid-auto-flow: dense` for better packing.
- All cards remain single-column (no hero spanning).

## 2. Card Anatomy

**New structure (top to bottom):**
1. **Thumbnail header** (YouTube only): 16:9 `object-fit: cover`, ~140px tall. Skipped for Reddit/HN.
2. **Left accent border** (3px): Replaces inline score bar. Green (score >= 0.7), gold (0.4–0.7), transparent (< 0.4). Exact score shown on hover tooltip.
3. **Source row**: Source badge + relative timestamp (right-aligned).
4. **Metrics row**: Upvotes, comment count, view count (source-dependent).
5. **Title**: Serif, bolder, slightly larger.
6. **Summary**: Flexible height, no clipping (Reddit/HN still clamped to 3 lines for brevity, YouTube shows full summary).
7. **Divider**: Subtle 1px rule.
8. **Actions row**: Star rating + bookmark + dismiss. Author shown on hover only.

**Removed:**
- Inline score bar (replaced by accent border)
- Author from footer (available on hover)

## 3. Masthead & Navigation

- Sticky masthead with `backdrop-filter: blur(8px)` and slight transparency for lighter feel while scrolling.
- Filter nav becomes segmented control pills with rounded backgrounds and count badges (e.g., "Reddit (12)").
- Add client-side search input to filter nav (right side) — filters article titles in real-time.
- Font size controls move into a small settings/gear dropdown to declutter the header.

## 4. Interactions & Microanimations

- **Dismiss**: Card slides left + fades (not just fade). Undo toast gets a visible countdown progress bar.
- **Bookmark**: Star scale-bounce (1.0 → 1.3 → 1.0, 200ms). Brief golden glow on card border.
- **Card hover**: Subtle shadow lift (`box-shadow: 0 2px 8px rgba(0,0,0,0.08)`) and 1px upward translate.
- **Tab switching**: Crossfade between Fresh/Archive panels.
- **Keyboard nav**: Replace harsh outline with thin accent underline on focused card.

## 5. Dark Mode

- Add manual sun/moon toggle in masthead, stored in localStorage, overrides system preference.
- Refined palette: deeper warm blacks (`#141210`), softer text (`#ddd5c4`).
- Card backgrounds slightly lighter than page background in dark mode.
- Thumbnails get subtle dark overlay border to prevent harsh bright rectangles.

## 6. Empty States & Polish

- Empty states get a simple SVG newspaper icon illustration.
- Footer simplified to single line.
- Consistent spacing and typography scale throughout.

---

## Files to Modify

- `app/static/style.css` — Major changes: card layout, grid, accent borders, masthead, dark mode, animations.
- `app/templates/base.html` — Masthead restructuring, dark mode toggle, settings dropdown.
- `app/templates/newspaper.html` — Card macro rewrite, search input, filter pills with counts, thumbnail rendering.
- `app/static/rating.js` — Minor: coordinate with new card structure if needed.
- `app/routes/newspaper.py` — Pass source counts to template for filter pill badges.

## Files Unchanged

- `app/database.py` — No schema changes.
- `app/templates/admin.html` — Admin page not in scope for this redesign.
- `app/routes/admin.py` — Not in scope.

## Constraints

- Pure CSS + vanilla JS. No framework dependencies.
- Must preserve all existing functionality: star ratings, bookmarks (localStorage), dismiss/undo, keyboard nav, font size persistence.
- `thumbnail_url` column already exists in DB — just needs to be rendered.
- Admin page is out of scope (can be a follow-up).
