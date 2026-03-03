import { useState, useCallback, useMemo } from "react"
import { useSearchParams } from "react-router-dom"
import { Layout } from "@/components/Layout"
import { ArticleGrid } from "@/components/ArticleGrid"
import { SearchBar } from "@/components/SearchBar"
import { UndoToast } from "@/components/UndoToast"
import { useArticles } from "@/hooks/useArticles"
import { useBookmarks } from "@/hooks/useBookmarks"
import { useKeyboardNav } from "@/hooks/useKeyboardNav"
import { dismissArticle, restoreArticle, removeSource } from "@/api/client"
import type { ArticleItem } from "@/types"

export function NewspaperPage() {
  const [searchParams] = useSearchParams()
  const source = searchParams.get("source") || "all"
  const { data, loading, error, reload } = useArticles(source)
  const { bookmarks, toggle: toggleBookmark, has: bookmarkHas } = useBookmarks()
  const [search, setSearch] = useState("")
  const [dismissedIds, setDismissedIds] = useState<Set<number>>(new Set())
  const [undoInfo, setUndoInfo] = useState<{ articleId: number; visible: boolean }>({ articleId: 0, visible: false })

  // Filter articles
  const filterItems = useCallback((items: ArticleItem[]): ArticleItem[] => {
    let filtered = items

    // Remove dismissed articles (optimistic)
    filtered = filtered.filter((item) => !dismissedIds.has(item.article.id))

    // Bookmarks filter
    if (source === "bookmarks") {
      filtered = filtered.filter((item) => bookmarks.has(item.article.id))
    } else if (source !== "dismissed") {
      // Hide bookmarked articles from non-bookmark views
      filtered = filtered.filter((item) => !bookmarks.has(item.article.id))
    }

    // Search filter
    if (search.trim()) {
      const q = search.toLowerCase().trim()
      filtered = filtered.filter((item) => {
        const title = item.article.title?.toLowerCase() || ""
        const summary = item.article.summary?.toLowerCase() || ""
        return title.includes(q) || summary.includes(q)
      })
    }

    return filtered
  }, [dismissedIds, bookmarks, source, search])

  const freshFiltered = useMemo(() => filterItems(data?.fresh || []), [data?.fresh, filterItems])
  const archiveFiltered = useMemo(() => filterItems(data?.archive || []), [data?.archive, filterItems])

  // All visible article IDs for keyboard nav
  const visibleIds = useMemo(() => {
    return [...freshFiltered, ...archiveFiltered].map((item) => item.article.id)
  }, [freshFiltered, archiveFiltered])

  // Dismiss handler
  const handleDismiss = useCallback(async (id: number) => {
    setDismissedIds((prev) => new Set([...prev, id]))
    setUndoInfo({ articleId: id, visible: true })

    try {
      await dismissArticle(id)
    } catch (err) {
      console.error("Dismiss error:", err)
    }

    // Auto-hide toast
    setTimeout(() => {
      setUndoInfo((prev) => (prev.articleId === id ? { ...prev, visible: false } : prev))
    }, 4000)
  }, [])

  // Undo handler
  const handleUndo = useCallback(async () => {
    const { articleId } = undoInfo
    setUndoInfo({ articleId: 0, visible: false })
    setDismissedIds((prev) => {
      const next = new Set(prev)
      next.delete(articleId)
      return next
    })
    try {
      await restoreArticle(articleId)
    } catch (err) {
      console.error("Restore error:", err)
    }
  }, [undoInfo])

  // Restore handler (for dismissed view)
  const handleRestore = useCallback(async (id: number) => {
    setDismissedIds((prev) => new Set([...prev, id]))
    try {
      await restoreArticle(id)
    } catch (err) {
      console.error("Restore error:", err)
    }
  }, [])

  // Remove source handler
  const handleRemoveSource = useCallback(async (sourceId: number, sourceName: string) => {
    if (!confirm(`Remove source "${sourceName}" and hide all its articles?`)) return
    try {
      await removeSource(sourceId)
      reload()
    } catch (err) {
      console.error("Remove source error:", err)
    }
  }, [reload])

  // Keyboard nav
  const kbOptions = useMemo(() => ({
    onDismiss: source === "dismissed" ? undefined : handleDismiss,
    onBookmark: toggleBookmark,
  }), [source, handleDismiss, toggleBookmark])

  const { focusIdx, hintVisible } = useKeyboardNav(visibleIds, kbOptions)

  if (loading && !data) {
    return (
      <Layout showFilters>
        <div className="text-center py-16" style={{ color: "var(--ink-muted)" }}>Loading...</div>
      </Layout>
    )
  }

  if (error) {
    return (
      <Layout showFilters>
        <div className="text-center py-16" style={{ color: "var(--accent)" }}>Error: {error}</div>
      </Layout>
    )
  }

  return (
    <Layout
      showFilters
      lastFetchedUtc={data?.last_fetched_utc}
      sourceCounts={data?.source_counts}
      version={data?.version}
    >
      {/* Search bar in filter area */}
      <div className="flex justify-end mb-4">
        <SearchBar value={search} onChange={setSearch} />
      </div>

      <ArticleGrid
        fresh={freshFiltered}
        archive={archiveFiltered}
        activeFilter={source}
        bookmarkHas={bookmarkHas}
        focusIdx={focusIdx}
        visibleIds={visibleIds}
        onDismiss={handleDismiss}
        onRestore={handleRestore}
        onBookmark={toggleBookmark}
        onRemoveSource={handleRemoveSource}
      />

      <UndoToast visible={undoInfo.visible} onUndo={handleUndo} />

      {/* Keyboard hint */}
      <div
        className="fixed bottom-6 right-6 rounded"
        style={{
          fontFamily: "var(--font-sans)", fontSize: "0.7rem", color: "var(--ink-muted)",
          background: "var(--cream-dark)", border: "1px solid var(--rule)",
          padding: "0.4rem 0.7rem", lineHeight: 1.8,
          opacity: hintVisible ? 1 : 0, transition: "opacity 0.3s", pointerEvents: "none",
        }}
      >
        <kbd className="inline-block rounded-sm px-1" style={{ background: "var(--rule)", fontSize: "0.65rem", fontFamily: "monospace" }}>j</kbd>/<kbd className="inline-block rounded-sm px-1" style={{ background: "var(--rule)", fontSize: "0.65rem", fontFamily: "monospace" }}>k</kbd> navigate{" "}
        <kbd className="inline-block rounded-sm px-1" style={{ background: "var(--rule)", fontSize: "0.65rem", fontFamily: "monospace" }}>Enter</kbd> open{" "}
        <kbd className="inline-block rounded-sm px-1" style={{ background: "var(--rule)", fontSize: "0.65rem", fontFamily: "monospace" }}>d</kbd> dismiss{" "}
        <kbd className="inline-block rounded-sm px-1" style={{ background: "var(--rule)", fontSize: "0.65rem", fontFamily: "monospace" }}>b</kbd> bookmark{" "}
        <kbd className="inline-block rounded-sm px-1" style={{ background: "var(--rule)", fontSize: "0.65rem", fontFamily: "monospace" }}>?</kbd> hide
      </div>
    </Layout>
  )
}
