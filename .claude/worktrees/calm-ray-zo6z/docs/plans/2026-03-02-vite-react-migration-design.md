# Vite/React Migration Design

**Date:** 2026-03-02
**Approach:** Big Bang — build full React app, then swap out Jinja2 templates

## Summary

Migrate the AI Newspaper frontend from server-rendered Jinja2 templates + vanilla JS to a React SPA built with Vite. The existing newspaper aesthetic is evolved (modernized) rather than replicated or redesigned from scratch.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Visual style | Evolve (modernize newspaper look) | Keep editorial spirit, improve polish |
| Dev setup | Vite proxy to FastAPI | Standard, simple, preserves HMR |
| Routing | React Router | URL-based nav for / and /admin |
| State management | React state + context | App complexity doesn't warrant external libs |
| Production serving | FastAPI serves built files | Single process, simple deployment |
| Migration strategy | Big Bang | Clean break, build everything then swap |

## 1. Backend API Layer

### New JSON Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `GET /api/articles?source=` | GET | Articles list (fresh/archive split, with comments) |
| `GET /api/articles/counts` | GET | Per-source article counts |
| `GET /api/articles/last-fetched` | GET | Last fetch timestamp |

### Existing Endpoints (keep as-is or re-mount under /api/)

- `DELETE /dismiss/{id}` — dismiss article
- `POST /restore/{id}` — restore dismissed article
- `POST /rate/{id}` — rate article (1-5)
- `DELETE /source/{id}` — remove source + articles
- `POST /admin/fetch-now` — trigger manual fetch
- `GET /admin/fetch-status` — poll fetch progress
- `POST /admin/schedule` — set auto-fetch time
- `POST /admin/cookies/*` — YouTube cookies management
- `POST /admin/channel/*` — YouTube channel management
- `POST /admin/reddit/*` — Reddit subreddit management
- `POST /admin/source/*` — Source management
- `POST /admin/keyword/*` — Keyword management
- `POST /admin/weights/save` — Bulk weight save

### Production Serving

- FastAPI mounts `site/dist/` as static files
- Catch-all route returns `index.html` for React Router
- Jinja2 template routes removed after cutover

## 2. React App Architecture

### Project Structure

```
site/src/
├── main.tsx                    # Entry point, router setup
├── index.css                   # Tailwind imports + global styles
├── api/
│   └── client.ts               # Fetch wrapper for all API calls
├── hooks/
│   ├── useArticles.ts          # Fetch & cache articles
│   ├── useBookmarks.ts         # localStorage bookmarks
│   ├── useTheme.ts             # Dark/light mode toggle
│   ├── useFontSize.ts          # Font size preference
│   └── useKeyboardNav.ts       # j/k/d/b keyboard shortcuts
├── components/
│   ├── Layout.tsx              # Header, footer, theme/font controls
│   ├── ArticleCard.tsx         # Single article card
│   ├── ArticleGrid.tsx         # Grid of cards + search + tabs
│   ├── SourceBadge.tsx         # Reddit/YouTube/HN badge
│   ├── ScoreBar.tsx            # Relevancy score indicator
│   ├── StarRating.tsx          # 1-5 star rating widget
│   ├── SearchBar.tsx           # Client-side article search
│   ├── SourceFilter.tsx        # Source tab bar
│   ├── UndoToast.tsx           # Dismissal undo notification
│   └── admin/
│       ├── AdminLayout.tsx     # Admin page layout
│       ├── FetchControl.tsx    # Manual fetch + scheduling
│       ├── CostTracker.tsx     # API cost display
│       ├── ChannelManager.tsx  # YouTube channels CRUD
│       ├── SubredditManager.tsx # Reddit subreddits CRUD
│       ├── SourceManager.tsx   # Source weights + management
│       └── KeywordManager.tsx  # Keyword weights + management
├── pages/
│   ├── NewspaperPage.tsx       # Main view
│   └── AdminPage.tsx           # Admin dashboard
└── types/
    └── index.ts                # TypeScript interfaces
```

### Routing

- `/` → NewspaperPage (with `?source=` query param)
- `/admin` → AdminPage

### Key Features

All current features are carried over:
- Dark/light mode (CSS variables + useTheme hook)
- Font size controls (localStorage + useFontSize hook)
- Keyboard navigation j/k/Enter/d/b/? (useKeyboardNav hook)
- Client-side article search
- Bookmarks in localStorage
- Undo toast for dismiss (4-second window)
- Optimistic UI for ratings and dismiss
- Fresh/Archive tab switching (<=7 days / >7 days)
- Source filtering with counts
- Star ratings (1-5)
- Top comments display per article

## 3. Visual Design Direction

### Preserved

- Newspaper-inspired card grid layout
- Source-specific accent colors (Reddit #ff4500, YouTube #cc0000, HN #ff6600)
- Cream/ink color palette foundation
- Serif fonts for masthead/headings

### Evolved

- Cleaner card design with subtle shadows (not heavy borders)
- Better spacing and whitespace via Tailwind spacing scale
- Sans-serif body text for readability
- Smoother dark mode transitions
- Modern score bar and rating widget styling
- Subtle hover animations on cards
- Mobile-first responsive breakpoints

### Tailwind Approach

- Custom theme extending defaults (newspaper colors)
- CSS custom properties for dark mode toggle
- Utility-first styling, minimal custom CSS

## 4. Development & Deployment

### Development

- Vite dev server (port 5173) proxies to FastAPI (port 8000)
- `vite.config.ts` server.proxy for `/api/*`, `/rate/*`, `/dismiss/*`, `/restore/*`, `/source/*`, `/admin/*`
- Run both: `cd site && npm run dev` + `uvicorn app.main:app`

### Production

- `cd site && npm run build` → `site/dist/`
- FastAPI serves `site/dist/` as static files
- Catch-all returns `index.html` for client-side routing

### Cutover

1. Build full React app in `site/`
2. Add JSON API routes to FastAPI
3. Configure FastAPI to serve `site/dist/`
4. Remove Jinja2 template routes
5. Archive/remove `app/templates/` and `app/static/`

## Dependencies

New npm packages needed:
- `react-router-dom` — client-side routing

No other external libraries planned (state via built-in React, styling via Tailwind).
