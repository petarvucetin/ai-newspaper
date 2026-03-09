# Vite/React Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the Jinja2 + vanilla JS frontend with a React SPA built on the existing Vite scaffold in `site/`.

**Architecture:** React SPA with React Router for `/` and `/admin` pages. Vite dev server proxies API requests to FastAPI. In production, FastAPI serves the built `site/dist/` folder. All state managed via React hooks and context — no external state library.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 4, React Router, Vite 7

---

### Task 1: Install Dependencies & Configure Vite Proxy

**Files:**
- Modify: `site/package.json`
- Modify: `site/vite.config.ts`

**Step 1: Install react-router-dom**

Run: `cd site && npm install react-router-dom`

**Step 2: Configure Vite dev server proxy**

Edit `site/vite.config.ts`:

```ts
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/rate": "http://localhost:8000",
      "/dismiss": "http://localhost:8000",
      "/restore": "http://localhost:8000",
      "/source": "http://localhost:8000",
      "/admin": "http://localhost:8000",
    },
  },
})
```

**Step 3: Verify dev server starts**

Run: `cd site && npm run dev`
Expected: Vite dev server starts on port 5173 with no errors.

**Step 4: Commit**

```bash
git add site/package.json site/package-lock.json site/vite.config.ts
git commit -m "chore: install react-router-dom and configure Vite proxy"
```

---

### Task 2: Add JSON API Endpoints to FastAPI

**Files:**
- Create: `app/routes/api.py`
- Modify: `app/main.py:46` (add router include)

**Step 1: Create the API router**

Create `app/routes/api.py` with these endpoints:

```python
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query
from app.database import (
    get_articles, get_dismissed_articles, get_comments_for_articles, db_conn
)

router = APIRouter(prefix="/api")


def _split_by_age(articles):
    now = datetime.now(timezone.utc)
    fresh_cutoff = now - timedelta(days=7)
    old_cutoff = now - timedelta(days=10)
    fresh, archive = [], []
    for a in articles:
        pub = a["published_at"]
        if not pub:
            fresh.append({"article": _row_to_dict(a), "old": False})
            continue
        try:
            dt = datetime.strptime(pub, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            fresh.append({"article": _row_to_dict(a), "old": False})
            continue
        if dt >= fresh_cutoff:
            fresh.append({"article": _row_to_dict(a), "old": False})
        else:
            archive.append({"article": _row_to_dict(a), "old": dt < old_cutoff})
    return fresh, archive


def _row_to_dict(row) -> dict:
    return dict(row)


def _attach_comments(items: list[dict]) -> None:
    article_ids = [item["article"]["id"] for item in items if item.get("article")]
    if not article_ids:
        return
    comments_map = get_comments_for_articles(article_ids)
    for item in items:
        aid = item["article"]["id"]
        item["comments"] = comments_map.get(aid, [])


def _source_counts() -> dict[str, int]:
    with db_conn() as con:
        rows = con.execute(
            "SELECT s.source_type, COUNT(*) as cnt "
            "FROM articles a JOIN sources s ON a.source_id = s.id "
            "WHERE COALESCE(a.dismissed, 0) = 0 "
            "GROUP BY s.source_type"
        ).fetchall()
    counts = {r["source_type"]: r["cnt"] for r in rows}
    yt = counts.pop("youtube", 0) + counts.pop("youtube_channel", 0)
    if yt:
        counts["youtube"] = yt
    return counts


def _last_fetched_utc() -> str | None:
    with db_conn() as con:
        row = con.execute("SELECT MAX(fetched_at) AS ts FROM articles").fetchone()
    return row["ts"] if row else None


@router.get("/articles")
async def api_articles(source: str = Query(default="all")):
    if source == "dismissed":
        articles = get_dismissed_articles()
        fresh = [{"article": _row_to_dict(a), "old": False} for a in articles]
        archive = []
    else:
        source_type = None if source in ("all", "bookmarks") else source
        articles = get_articles(limit=200, source_type=source_type)
        fresh, archive = _split_by_age(articles)
    _attach_comments(fresh)
    _attach_comments(archive)
    return {
        "fresh": fresh,
        "archive": archive,
        "active_filter": source,
        "last_fetched_utc": _last_fetched_utc(),
        "source_counts": _source_counts(),
    }


@router.get("/admin/data")
async def api_admin_data():
    """Return all admin page data as JSON (no auth — reuse existing admin auth on admin/* routes)."""
    from app.database import (
        get_sources, get_keyword_weights, get_youtube_channels, get_reddit_sources,
        get_setting, get_api_usage_summary,
    )
    from app import config
    from app.routes.admin import _cookies_status, _last_fetched

    all_sources = get_sources()
    sources = [dict(s) for s in all_sources if s["source_type"] not in ("youtube_channel", "reddit")]
    channels = [dict(ch) for ch in get_youtube_channels()]
    reddit_sources = [dict(r) for r in get_reddit_sources()]
    keywords = [dict(kw) for kw in get_keyword_weights()]
    default_time = config.get("schedule.fetch_time", "07:00")
    schedule_time = get_setting("schedule.fetch_time", default_time)
    auto_enabled = get_setting("schedule.auto_enabled", "1") == "1"

    return {
        "sources": sources,
        "channels": channels,
        "reddit_sources": reddit_sources,
        "keywords": keywords,
        "last_fetched": _last_fetched(),
        "schedule_time": schedule_time,
        "auto_enabled": auto_enabled,
        "cookies_status": _cookies_status(),
        "api_usage": get_api_usage_summary(),
    }
```

**Step 2: Register the API router in main.py**

Add to `app/main.py` after the existing router imports:

```python
from app.routes import newspaper, rating, admin, dismiss, api
```

And after the existing `app.include_router` lines:

```python
app.include_router(api.router)
```

**Step 3: Test the API endpoint**

Run the FastAPI server and test:
```bash
curl http://localhost:8000/api/articles | python -m json.tool | head -30
```
Expected: JSON response with `fresh`, `archive`, `active_filter`, `last_fetched_utc`, `source_counts` keys.

**Step 4: Commit**

```bash
git add app/routes/api.py app/main.py
git commit -m "feat: add JSON API endpoints for React frontend"
```

---

### Task 3: TypeScript Types & API Client

**Files:**
- Create: `site/src/types/index.ts`
- Create: `site/src/api/client.ts`

**Step 1: Define TypeScript interfaces**

Create `site/src/types/index.ts`:

```ts
export interface Article {
  id: number
  source_id: number
  external_id: string
  title: string
  url: string
  summary: string | null
  author: string | null
  published_at: string | null
  fetched_at: string
  relevancy_score: number
  display_score: number
  thumbnail_url: string | null
  num_comments: number
  upvotes: number
  source_name: string
  source_type: string
  user_rating: number | null
  dismissed: number
  dismissed_at: string | null
  auto_dismissed: number
}

export interface Comment {
  article_id: number
  author: string
  body: string
  score: number
  comment_url: string
}

export interface ArticleItem {
  article: Article
  old: boolean
  comments?: Comment[]
}

export interface ArticlesResponse {
  fresh: ArticleItem[]
  archive: ArticleItem[]
  active_filter: string
  last_fetched_utc: string | null
  source_counts: Record<string, number>
}

export interface Source {
  id: number
  name: string
  source_type: string
  identifier: string
  weight: number
  enabled: number
  created_at: string
}

export interface KeywordWeight {
  id: number
  keyword: string
  weight: number
  hits: number
}

export interface CookiesStatus {
  exists: boolean
  age_days: number | null
  warning: boolean
}

export interface ApiUsageRow {
  model: string
  purpose: string
  input_tokens: number
  output_tokens: number
  cost_usd: number
  calls: number
}

export interface ApiUsageSummary {
  totals: ApiUsageRow[]
  overall: {
    total_cost: number | null
    total_input: number | null
    total_output: number | null
    total_calls: number | null
  }
  daily: { day: string; cost_usd: number; calls: number }[]
}

export interface AdminData {
  sources: Source[]
  channels: Source[]
  reddit_sources: Source[]
  keywords: KeywordWeight[]
  last_fetched: string | null
  schedule_time: string
  auto_enabled: boolean
  cookies_status: CookiesStatus
  api_usage: ApiUsageSummary
}

export interface FetchStatus {
  status: "idle" | "running" | "done" | "error"
  log: string[]
  inserted: number
  skipped: number
  total: number
  error: string
  elapsed: number
}
```

**Step 2: Create the API client**

Create `site/src/api/client.ts`:

```ts
import type { ArticlesResponse, AdminData, FetchStatus } from "@/types"

const BASE = ""  // Vite proxy handles routing to FastAPI

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${url}`, {
    credentials: "include",
    ...options,
  })
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
  return resp.json()
}

// --- Articles ---
export function fetchArticles(source = "all"): Promise<ArticlesResponse> {
  return request(`/api/articles?source=${encodeURIComponent(source)}`)
}

export function dismissArticle(articleId: number): Promise<void> {
  return request(`/dismiss/${articleId}`, { method: "DELETE" })
}

export function restoreArticle(articleId: number): Promise<void> {
  return request(`/restore/${articleId}`, { method: "POST" })
}

export function rateArticle(articleId: number, score: number): Promise<void> {
  return request(`/rate/${articleId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ score }),
  })
}

export function removeSource(sourceId: number): Promise<void> {
  return request(`/source/${sourceId}`, { method: "DELETE" })
}

// --- Admin ---
export function fetchAdminData(): Promise<AdminData> {
  return request("/api/admin/data")
}

export function startFetch(): Promise<{ status: string }> {
  return request("/admin/fetch-now", { method: "POST" })
}

export function fetchFetchStatus(): Promise<FetchStatus> {
  return request("/admin/fetch-status")
}

export function saveSchedule(fetchTime: string, autoEnabled: boolean): Promise<void> {
  const form = new URLSearchParams()
  form.set("fetch_time", fetchTime)
  form.set("auto_enabled", autoEnabled ? "1" : "0")
  return request("/admin/schedule", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  })
}

export function uploadCookies(file: File): Promise<void> {
  const form = new FormData()
  form.append("cookies_file", file)
  return request("/admin/cookies/upload", { method: "POST", body: form })
}

export function deleteCookies(): Promise<void> {
  return request("/admin/cookies/delete", { method: "POST" })
}

export function addChannel(handle: string): Promise<void> {
  const form = new URLSearchParams()
  form.set("channel", handle)
  return request("/admin/channel/add", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  })
}

export function pinChannel(sourceId: number): Promise<void> {
  return request(`/admin/channel/${sourceId}/pin`, { method: "POST" })
}

export function unpinChannel(sourceId: number): Promise<void> {
  return request(`/admin/channel/${sourceId}/unpin`, { method: "POST" })
}

export function deleteChannel(sourceId: number): Promise<void> {
  return request(`/admin/channel/${sourceId}/delete`, { method: "POST" })
}

export function addSubreddit(name: string): Promise<void> {
  const form = new URLSearchParams()
  form.set("subreddit", name)
  return request("/admin/reddit/add", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  })
}

export function toggleReddit(sourceId: number): Promise<void> {
  return request(`/admin/reddit/${sourceId}/toggle`, { method: "POST" })
}

export function deleteReddit(sourceId: number): Promise<void> {
  return request(`/admin/reddit/${sourceId}/delete`, { method: "POST" })
}

export function addSource(name: string, sourceType: string, identifier: string, weight: number): Promise<void> {
  const form = new URLSearchParams()
  form.set("name", name)
  form.set("source_type", sourceType)
  form.set("identifier", identifier)
  form.set("weight", String(weight))
  return request("/admin/source/add", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  })
}

export function toggleSource(sourceId: number): Promise<void> {
  return request(`/admin/source/${sourceId}/toggle`, { method: "POST" })
}

export function deleteSource(sourceId: number): Promise<void> {
  return request(`/admin/source/${sourceId}/delete`, { method: "POST" })
}

export function addKeyword(keyword: string, weight: number): Promise<void> {
  const form = new URLSearchParams()
  form.set("keyword", keyword)
  form.set("weight", String(weight))
  return request("/admin/keyword/add", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  })
}

export function deleteKeyword(keywordId: number): Promise<void> {
  return request(`/admin/keyword/${keywordId}/delete`, { method: "POST" })
}

export function saveWeights(
  sources: { id: number; weight: number }[],
  keywords: { id: number; weight: number }[],
): Promise<{ ok: boolean; updated: number }> {
  return request("/admin/weights/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sources, keywords }),
  })
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd site && npx tsc --noEmit`
Expected: No type errors.

**Step 4: Commit**

```bash
git add site/src/types/index.ts site/src/api/client.ts
git commit -m "feat: add TypeScript types and API client"
```

---

### Task 4: React Hooks (Theme, Font Size, Bookmarks, Keyboard Nav)

**Files:**
- Create: `site/src/hooks/useTheme.ts`
- Create: `site/src/hooks/useFontSize.ts`
- Create: `site/src/hooks/useBookmarks.ts`
- Create: `site/src/hooks/useKeyboardNav.ts`
- Create: `site/src/hooks/useArticles.ts`

**Step 1: Create useTheme hook**

```ts
// site/src/hooks/useTheme.ts
import { useState, useEffect, useCallback } from "react"

const THEME_KEY = "ai-news-theme"

export function useTheme() {
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved) return saved === "dark"
    return window.matchMedia("(prefers-color-scheme: dark)").matches
  })

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
    localStorage.setItem(THEME_KEY, dark ? "dark" : "light")
  }, [dark])

  const toggle = useCallback(() => setDark((d) => !d), [])
  return { dark, toggle }
}
```

**Step 2: Create useFontSize hook**

```ts
// site/src/hooks/useFontSize.ts
import { useState, useEffect, useCallback } from "react"

const FONT_KEY = "ai-news-font-size"
const FONT_MIN = 11
const FONT_MAX = 22
const FONT_DEFAULT = 16

export function useFontSize() {
  const [size, setSize] = useState(() => {
    const saved = parseInt(localStorage.getItem(FONT_KEY) || "", 10)
    return saved || FONT_DEFAULT
  })

  useEffect(() => {
    document.documentElement.style.setProperty("--article-font-size", `${size}px`)
    localStorage.setItem(FONT_KEY, String(size))
  }, [size])

  const inc = useCallback(() => setSize((s) => Math.min(FONT_MAX, s + 1)), [])
  const dec = useCallback(() => setSize((s) => Math.max(FONT_MIN, s - 1)), [])
  return { size, inc, dec }
}
```

**Step 3: Create useBookmarks hook**

```ts
// site/src/hooks/useBookmarks.ts
import { useState, useCallback } from "react"

const BOOKMARK_KEY = "ai-news-bookmarks"

function load(): Set<number> {
  try {
    return new Set(JSON.parse(localStorage.getItem(BOOKMARK_KEY) || "[]"))
  } catch {
    return new Set()
  }
}

function save(set: Set<number>) {
  localStorage.setItem(BOOKMARK_KEY, JSON.stringify([...set]))
}

export function useBookmarks() {
  const [bookmarks, setBookmarks] = useState(load)

  const toggle = useCallback((id: number) => {
    setBookmarks((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      save(next)
      return next
    })
  }, [])

  const has = useCallback((id: number) => bookmarks.has(id), [bookmarks])

  return { bookmarks, toggle, has }
}
```

**Step 4: Create useKeyboardNav hook**

```ts
// site/src/hooks/useKeyboardNav.ts
import { useState, useEffect, useCallback, useRef } from "react"

interface UseKeyboardNavOptions {
  onDismiss?: (id: number) => void
  onBookmark?: (id: number) => void
  onOpen?: (url: string) => void
}

export function useKeyboardNav(
  articleIds: number[],
  options: UseKeyboardNavOptions,
) {
  const [focusIdx, setFocusIdx] = useState(-1)
  const [hintVisible, setHintVisible] = useState(false)
  const idsRef = useRef(articleIds)
  idsRef.current = articleIds

  const focus = useCallback((idx: number) => {
    const ids = idsRef.current
    if (ids.length === 0) return
    setFocusIdx(Math.max(0, Math.min(idx, ids.length - 1)))
  }, [])

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement).tagName)) return

      if (e.key === "?") {
        setHintVisible((v) => !v)
        return
      }
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault()
        setFocusIdx((i) => {
          const next = i < 0 ? 0 : Math.min(i + 1, idsRef.current.length - 1)
          return next
        })
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault()
        setFocusIdx((i) => Math.max(0, i - 1))
      } else if (e.key === "Enter") {
        setFocusIdx((i) => {
          if (i >= 0 && options.onOpen) {
            const el = document.querySelector(`[data-article-id="${idsRef.current[i]}"] .article-title a`) as HTMLAnchorElement
            if (el) window.open(el.href, "_blank", "noopener")
          }
          return i
        })
      } else if (e.key === "d") {
        setFocusIdx((i) => {
          if (i >= 0 && options.onDismiss) options.onDismiss(idsRef.current[i])
          return i
        })
      } else if (e.key === "b") {
        setFocusIdx((i) => {
          if (i >= 0 && options.onBookmark) options.onBookmark(idsRef.current[i])
          return i
        })
      }
    }

    window.addEventListener("keydown", handleKey)
    return () => window.removeEventListener("keydown", handleKey)
  }, [options, focus])

  return { focusIdx, hintVisible }
}
```

**Step 5: Create useArticles hook**

```ts
// site/src/hooks/useArticles.ts
import { useState, useEffect, useCallback } from "react"
import { fetchArticles } from "@/api/client"
import type { ArticlesResponse } from "@/types"

export function useArticles(source: string) {
  const [data, setData] = useState<ArticlesResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetchArticles(source)
      setData(resp)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load articles")
    } finally {
      setLoading(false)
    }
  }, [source])

  useEffect(() => { load() }, [load])

  return { data, loading, error, reload: load }
}
```

**Step 6: Verify TypeScript compiles**

Run: `cd site && npx tsc --noEmit`
Expected: No type errors.

**Step 7: Commit**

```bash
git add site/src/hooks/
git commit -m "feat: add React hooks for theme, bookmarks, keyboard nav, articles"
```

---

### Task 5: Tailwind Global Styles & CSS Custom Properties

**Files:**
- Modify: `site/src/index.css`

**Step 1: Set up Tailwind with newspaper theme custom properties**

Replace `site/src/index.css` with:

```css
@import "tailwindcss";

/* Newspaper theme — CSS custom properties */
:root {
  --article-font-size: 16px;
  --cream: #f5f0e8;
  --cream-dark: #ede7d5;
  --ink: #1a1a1a;
  --ink-light: #444;
  --ink-muted: #777;
  --rule: #c8bea0;
  --accent: #8b1a1a;
  --reddit-color: #ff4500;
  --youtube-color: #cc0000;
  --hn-color: #ff6600;
  --badge-text: #fff;
  --star-off: #c8bea0;
  --star-on: #c9a227;
  --font-serif: 'Georgia', 'Times New Roman', serif;
  --font-sans: 'Helvetica Neue', Arial, sans-serif;
  --score-low: #c8bea0;
  --score-mid: #c9a227;
  --score-high: #2a7a2a;
}

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

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--cream);
  color: var(--ink);
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: 1.6;
}

/* Scrollbar styling for dark mode */
html.dark ::-webkit-scrollbar { width: 6px; }
html.dark ::-webkit-scrollbar-thumb { background: var(--rule); border-radius: 3px; }

/* Visited link color */
a:visited { color: var(--ink-muted); }
```

**Step 2: Commit**

```bash
git add site/src/index.css
git commit -m "feat: add Tailwind global styles with newspaper theme variables"
```

---

### Task 6: Layout Component (Header, Footer, Theme/Font Controls)

**Files:**
- Create: `site/src/components/Layout.tsx`

**Step 1: Build the Layout component**

This component replicates `base.html` — sticky masthead with title, nav links, theme toggle, font size controls, settings dropdown, and footer.

```tsx
// site/src/components/Layout.tsx
import { useState, type ReactNode } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useTheme } from "@/hooks/useTheme"
import { useFontSize } from "@/hooks/useFontSize"

interface LayoutProps {
  children: ReactNode
  lastFetchedUtc?: string | null
  sourceCounts?: Record<string, number>
  showFilters?: boolean
}

export function Layout({ children, lastFetchedUtc, sourceCounts, showFilters = false }: LayoutProps) {
  const { dark, toggle: toggleTheme } = useTheme()
  const { inc, dec } = useFontSize()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [searchParams] = useSearchParams()
  const activeFilter = searchParams.get("source") || "all"

  const lastFetchedStr = lastFetchedUtc
    ? new Date(lastFetchedUtc.replace(" ", "T") + "Z").toLocaleString([], {
        weekday: "long", year: "numeric", month: "long",
        day: "numeric", hour: "2-digit", minute: "2-digit",
      })
    : ""

  return (
    <div className="min-h-screen flex flex-col">
      {/* Masthead */}
      <header
        className="sticky top-0 z-50 border-b-[3px] border-double px-6 pt-3"
        style={{
          background: "color-mix(in srgb, var(--cream) 85%, transparent)",
          backdropFilter: "blur(8px)",
          WebkitBackdropFilter: "blur(8px)",
          borderColor: "var(--ink)",
        }}
      >
        <div
          className="flex items-center justify-between flex-wrap gap-2 pb-2"
          style={{ borderBottom: "1px solid var(--rule)" }}
        >
          {/* Left: edition info */}
          <div className="min-w-[120px]" style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", color: "var(--ink-muted)" }}>
            <span>Daily Edition &mdash; {lastFetchedStr}</span>
          </div>

          {/* Center: title */}
          <h1
            className="flex-1 text-center uppercase tracking-tight"
            style={{ fontFamily: "var(--font-serif)", fontSize: "clamp(1.8rem, 5vw, 3.2rem)", fontWeight: 900, letterSpacing: "-0.02em", color: "var(--ink)" }}
          >
            <Link to="/" className="no-underline" style={{ color: "inherit" }}>The AI Intelligence</Link>
          </h1>

          {/* Right: nav + controls */}
          <div className="flex items-center gap-2 min-w-[120px] justify-end" style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem" }}>
            <Link to="/" style={{ color: "var(--accent)", fontWeight: 600, textDecoration: "none" }}>Home</Link>
            <Link to="/admin" style={{ color: "var(--accent)", fontWeight: 600, textDecoration: "none" }}>Admin</Link>

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              title="Toggle dark/light mode"
              className="w-7 h-7 flex items-center justify-center rounded-full cursor-pointer"
              style={{ border: "1px solid var(--rule)", color: "var(--ink-light)", fontSize: "0.9rem", background: "none", transition: "background 0.15s, color 0.15s" }}
            >
              {dark ? "\u2600" : "\u263E"}
            </button>

            {/* Settings dropdown */}
            <div className="relative">
              <button
                onClick={(e) => { e.stopPropagation(); setSettingsOpen((o) => !o) }}
                title="Settings"
                className="w-7 h-7 flex items-center justify-center rounded-full cursor-pointer"
                style={{ border: "1px solid var(--rule)", color: "var(--ink-light)", fontSize: "0.9rem", background: "none" }}
              >
                &#9881;
              </button>
              {settingsOpen && (
                <div
                  className="absolute right-0 top-[110%] rounded-md p-2.5 z-50 min-w-[140px]"
                  style={{ background: "var(--cream)", border: "1px solid var(--rule)", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="flex items-center gap-1">
                    <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", color: "var(--ink-muted)" }}>Font size</span>
                    <button onClick={dec} className="px-1.5 py-0.5 rounded-sm cursor-pointer" style={{ border: "1px solid var(--rule)", color: "var(--ink-light)", fontFamily: "var(--font-sans)", fontSize: "0.7rem", fontWeight: 700, background: "none" }}>A&minus;</button>
                    <button onClick={inc} className="px-1.5 py-0.5 rounded-sm cursor-pointer" style={{ border: "1px solid var(--rule)", color: "var(--ink-light)", fontFamily: "var(--font-sans)", fontSize: "0.7rem", fontWeight: 700, background: "none" }}>A+</button>
                  </div>
                  <span style={{ fontSize: "0.65rem", color: "var(--ink-muted)", letterSpacing: "0.05em" }}>v0.2.0</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Filter nav */}
        {showFilters && (
          <nav className="flex items-center gap-1 py-1.5 flex-wrap">
            {[
              { key: "all", label: "All" },
              { key: "reddit", label: "Reddit" },
              { key: "youtube", label: "YouTube" },
              { key: "hackernews", label: "Hacker News" },
              { key: "bookmarks", label: "Bookmarks" },
              { key: "dismissed", label: "Dismissed" },
            ].map(({ key, label }) => (
              <Link
                key={key}
                to={`/?source=${key}`}
                className={`px-3 py-1 rounded-full no-underline text-sm transition-colors ${activeFilter === key ? "font-semibold" : ""}`}
                style={{
                  fontFamily: "var(--font-sans)",
                  fontSize: "0.78rem",
                  color: activeFilter === key ? "var(--cream)" : "var(--ink-light)",
                  background: activeFilter === key ? "var(--ink)" : "transparent",
                  border: "1px solid transparent",
                }}
              >
                {label}
                {sourceCounts && sourceCounts[key] && key !== "all" && key !== "bookmarks" && key !== "dismissed" && (
                  <span className="ml-0.5 opacity-70" style={{ fontSize: "0.65rem", fontWeight: 600 }}>{sourceCounts[key]}</span>
                )}
              </Link>
            ))}
          </nav>
        )}
      </header>

      {/* Main content */}
      <main className="flex-1 px-6 py-4">
        {children}
      </main>

      {/* Footer */}
      <footer
        className="text-center py-4 px-6"
        style={{ borderTop: "3px double var(--ink)", fontFamily: "var(--font-sans)", fontSize: "0.75rem", color: "var(--ink-muted)" }}
      >
        AI News Tracker &mdash; Daily AI digest
      </footer>
    </div>
  )
}
```

**Step 2: Verify it compiles**

Run: `cd site && npx tsc --noEmit`

**Step 3: Commit**

```bash
git add site/src/components/Layout.tsx
git commit -m "feat: add Layout component with masthead, theme, font controls"
```

---

### Task 7: Article Card Components (SourceBadge, StarRating, ArticleCard)

**Files:**
- Create: `site/src/components/SourceBadge.tsx`
- Create: `site/src/components/StarRating.tsx`
- Create: `site/src/components/ArticleCard.tsx`
- Create: `site/src/components/UndoToast.tsx`

**Step 1:** Build `SourceBadge.tsx` — small colored badge per source type.

**Step 2:** Build `StarRating.tsx` — 5-star widget with hover preview and optimistic locking (same behavior as `rating.js`).

**Step 3:** Build `ArticleCard.tsx` — full card matching the current design. Must include:
- Thumbnail for YouTube articles
- Source badge + relevancy label + auto-dismissed badge + relative time
- Metrics row (upvotes, views, comment count)
- Scrollable body with title, summary, and top comments
- Pinned footer with star widget, bookmark, dismiss/restore, remove source buttons
- Relevancy accent border (left border color based on score)
- `data-article-id` attribute for keyboard nav scrolling
- CSS class `kb-focus` when keyboard-focused

**Step 4:** Build `UndoToast.tsx` — fixed-bottom toast with undo button and 4-second progress bar.

Each of these components should use Tailwind utility classes combined with CSS custom properties from `index.css` for the newspaper palette. Use inline styles for CSS variables that Tailwind can't access (e.g., `style={{ color: "var(--ink-muted)" }}`).

Refer to the existing templates and CSS for exact behavior:
- `app/templates/newspaper.html:43-136` (article_card macro)
- `app/static/style.css:377-856` (card, toast, keyboard hint styles)
- `app/static/rating.js` (star rating behavior)

**Step 5: Commit**

```bash
git add site/src/components/SourceBadge.tsx site/src/components/StarRating.tsx site/src/components/ArticleCard.tsx site/src/components/UndoToast.tsx
git commit -m "feat: add ArticleCard, StarRating, SourceBadge, UndoToast components"
```

---

### Task 8: Article Grid & Newspaper Page

**Files:**
- Create: `site/src/components/ArticleGrid.tsx`
- Create: `site/src/components/SearchBar.tsx`
- Create: `site/src/pages/NewspaperPage.tsx`

**Step 1:** Build `SearchBar.tsx` — controlled input that filters articles client-side by title/summary.

**Step 2:** Build `ArticleGrid.tsx` — renders a CSS Grid of ArticleCard components. Handles:
- Fresh/Archive tab switching (with crossfade)
- Collapsed state for old articles (>10 days)
- "Expand All" button in archive
- Empty state when no articles

**Step 3:** Build `NewspaperPage.tsx` — composes Layout, ArticleGrid, SearchBar. Uses:
- `useArticles(source)` to fetch data (source from URL search params)
- `useBookmarks()` for bookmark state
- `useKeyboardNav()` for j/k/d/b navigation
- Dismiss/restore with optimistic UI and undo toast
- Bookmarks filtering (when source=bookmarks, only show bookmarked articles)
- Hide bookmarked articles from non-bookmark views

Refer to `app/templates/newspaper.html:150-545` for the full behavior specification.

**Step 4: Commit**

```bash
git add site/src/components/ArticleGrid.tsx site/src/components/SearchBar.tsx site/src/pages/NewspaperPage.tsx
git commit -m "feat: add NewspaperPage with article grid, search, tabs, keyboard nav"
```

---

### Task 9: Admin Page Components

**Files:**
- Create: `site/src/components/admin/FetchControl.tsx`
- Create: `site/src/components/admin/CostTracker.tsx`
- Create: `site/src/components/admin/ChannelManager.tsx`
- Create: `site/src/components/admin/SubredditManager.tsx`
- Create: `site/src/components/admin/SourceManager.tsx`
- Create: `site/src/components/admin/KeywordManager.tsx`
- Create: `site/src/pages/AdminPage.tsx`

**Step 1:** Build `FetchControl.tsx` — "Fetch Now" button + polling progress log + schedule form. Replicates:
- `startFetch()` function from `admin.html:337-386`
- Polling fetch-status every 1s, showing log lines in a dark terminal box
- Badge states (running/done/error)
- Schedule toggle (auto_enabled checkbox + time input)

**Step 2:** Build `CostTracker.tsx` — API cost summary display. Replicates `admin.html:30-67`.

**Step 3:** Build `ChannelManager.tsx` — YouTube channels table with add/pin/unpin/remove. Replicates `admin.html:117-178`.

**Step 4:** Build `SubredditManager.tsx` — Reddit subreddits table with add/toggle/remove. Replicates `admin.html:180-233`.

**Step 5:** Build `SourceManager.tsx` — Generic source weights table with add/toggle/remove. Replicates `admin.html:235-285`.

**Step 6:** Build `KeywordManager.tsx` — Keyword weights table with add/remove. Replicates `admin.html:287-324`.

**Step 7:** Build `AdminPage.tsx` — composes all admin components. Includes:
- Layout (without filters)
- Fetch data on mount via `fetchAdminData()`
- "Save All" bar for bulk weight changes (same dirty tracking as `admin.html:392-456`)
- Cookies management section

Refer to `app/templates/admin.html` for the full behavior specification and `app/static/style.css:882-1198` for admin styles.

**Step 8: Commit**

```bash
git add site/src/components/admin/ site/src/pages/AdminPage.tsx
git commit -m "feat: add AdminPage with fetch control, cost tracker, source managers"
```

---

### Task 10: Router Setup & App Entry Point

**Files:**
- Modify: `site/src/App.tsx`
- Modify: `site/src/main.tsx`

**Step 1: Set up React Router in App.tsx**

```tsx
// site/src/App.tsx
import { BrowserRouter, Routes, Route } from "react-router-dom"
import { NewspaperPage } from "@/pages/NewspaperPage"
import { AdminPage } from "@/pages/AdminPage"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<NewspaperPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </BrowserRouter>
  )
}
```

**Step 2: Verify main.tsx renders App**

`site/src/main.tsx` should already render `<App />`. Ensure it imports the updated App.

**Step 3: Run the dev server and test**

Run: `cd site && npm run dev`
With FastAPI running on port 8000, navigate to:
- `http://localhost:5173/` — should show the newspaper page
- `http://localhost:5173/admin` — should show the admin page

**Step 4: Fix any TypeScript or runtime errors**

Run: `cd site && npx tsc --noEmit`

**Step 5: Commit**

```bash
git add site/src/App.tsx site/src/main.tsx
git commit -m "feat: add React Router setup with newspaper and admin routes"
```

---

### Task 11: Production Serving from FastAPI

**Files:**
- Modify: `app/main.py`

**Step 1: Add SPA serving to FastAPI**

After the existing static files mount and router includes, add:

```python
from fastapi.responses import FileResponse

# Serve React SPA in production (site/dist must exist from `npm run build`)
spa_dir = Path(__file__).parent.parent / "site" / "dist"
if spa_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(spa_dir / "assets")), name="spa-assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Catch-all: serve index.html for client-side routing."""
        file = spa_dir / path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(spa_dir / "index.html")
```

**Important:** This catch-all MUST be registered AFTER all API routes, otherwise it will intercept API calls. The existing router includes (`newspaper.router`, `rating.router`, etc.) are registered first, so they take priority.

**Step 2: Build the React app**

Run: `cd site && npm run build`
Expected: `site/dist/` directory created with `index.html` and `assets/` folder.

**Step 3: Test production serving**

With FastAPI running, navigate to `http://localhost:8000/` — should serve the React SPA.
Navigate to `http://localhost:8000/api/articles` — should still return JSON.

**Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat: serve React SPA from FastAPI in production"
```

---

### Task 12: Clean Up Old Jinja2 Frontend

**Files:**
- Remove: `app/templates/newspaper.html`
- Remove: `app/templates/admin.html`
- Remove: `app/templates/base.html`
- Remove: `app/static/rating.js`
- Remove: `app/static/style.css`
- Modify: `app/main.py` (remove old static mount)
- Modify: `app/routes/newspaper.py` (remove HTML route or redirect to SPA)
- Modify: `app/routes/admin.py` (remove HTML route, keep API endpoints)

**Step 1: Remove old template and static files**

```bash
rm app/templates/newspaper.html app/templates/admin.html app/templates/base.html
rm app/static/rating.js app/static/style.css
rmdir app/templates app/static 2>/dev/null || true
```

**Step 2: Remove the old Jinja2 HTML routes**

In `app/routes/newspaper.py`, remove the `GET /` HTML route (or redirect it to the SPA).
In `app/routes/admin.py`, remove the `GET /admin` HTML route (keep all the POST endpoints).
Remove the Jinja2 `templates` objects and unused imports.

In `app/main.py`, remove the old static files mount:
```python
# Remove this line:
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
```

Also remove the `newspaper.router` include since it's no longer needed (articles are served via `api.router`).

**Step 3: Verify nothing is broken**

Run: `cd site && npm run build`
Start FastAPI and verify:
- `http://localhost:8000/` → React SPA loads
- `http://localhost:8000/api/articles` → JSON works
- `http://localhost:8000/admin` → React admin page loads
- Rating, dismiss, restore still work from the UI

**Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove old Jinja2 templates and static files"
```

---

### Task 13: Final Polish & Visual Refinement

**Files:**
- Various component files in `site/src/`

**Step 1: Visual QA pass**

Open the React app side-by-side with the old Jinja2 app (if still accessible). Verify:
- [ ] Card grid layout matches (3 columns, responsive to 2 and 1)
- [ ] Dark mode looks correct
- [ ] Source badges have correct colors
- [ ] Star rating widget works (hover preview, click to rate, locks after rating)
- [ ] Bookmark button works (toggles, hides from non-bookmark views)
- [ ] Dismiss works with undo toast (4-second window)
- [ ] Keyboard navigation works (j/k/Enter/d/b/?)
- [ ] Search filters articles in real-time
- [ ] Fresh/Archive tabs work with crossfade
- [ ] Old articles are collapsed in archive
- [ ] Admin fetch progress shows live log
- [ ] Weight changes show "unsaved" bar
- [ ] All admin CRUD operations work

**Step 2: Fix any visual discrepancies**

Adjust Tailwind classes and CSS custom property usage as needed.

**Step 3: Run TypeScript check**

Run: `cd site && npx tsc --noEmit`
Expected: No errors.

**Step 4: Production build**

Run: `cd site && npm run build`
Expected: Clean build, no warnings.

**Step 5: Commit**

```bash
git add -A
git commit -m "style: visual polish and QA fixes for React frontend"
```
