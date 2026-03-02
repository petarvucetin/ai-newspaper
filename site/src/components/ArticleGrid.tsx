import { useState } from "react"
import type { ArticleItem } from "@/types"
import { ArticleCard } from "./ArticleCard"

interface ArticleGridProps {
  fresh: ArticleItem[]
  archive: ArticleItem[]
  activeFilter: string
  bookmarkHas: (id: number) => boolean
  focusIdx: number
  visibleIds: number[]
  onDismiss: (id: number) => void
  onRestore: (id: number) => void
  onBookmark: (id: number) => void
  onRemoveSource: (sourceId: number, sourceName: string) => void
}

export function ArticleGrid({
  fresh, archive, activeFilter, bookmarkHas,
  focusIdx, visibleIds, onDismiss, onRestore, onBookmark, onRemoveSource,
}: ArticleGridProps) {
  const [activeTab, setActiveTab] = useState<"fresh" | "archive">("fresh")
  const [collapsedSet, setCollapsedSet] = useState<Set<number>>(() => {
    const set = new Set<number>()
    for (const item of archive) {
      if (item.old) set.add(item.article.id)
    }
    return set
  })
  const [allExpanded, setAllExpanded] = useState(false)
  const [fadingOut, setFadingOut] = useState(false)

  const isDismissedView = activeFilter === "dismissed"
  const hasArchive = archive.length > 0
  const items = activeTab === "fresh" ? fresh : archive

  if (fresh.length === 0 && archive.length === 0) {
    return (
      <div className="text-center py-16" style={{ color: "var(--ink-muted)" }}>
        <svg className="mx-auto mb-4" style={{ opacity: 0.5 }} width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 22h16a2 2 0 002-2V4a2 2 0 00-2-2H8a2 2 0 00-2 2v16a2 2 0 01-2 2zm0 0a2 2 0 01-2-2v-9c0-1.1.9-2 2-2h2"/>
          <line x1="10" y1="6" x2="18" y2="6"/>
          <line x1="10" y1="10" x2="18" y2="10"/>
          <line x1="10" y1="14" x2="14" y2="14"/>
        </svg>
        <h2 className="text-2xl mb-2">No articles yet</h2>
        <p>The daily fetch hasn&apos;t run yet. Visit <a href="/admin" style={{ color: "var(--accent)" }}>Admin</a> to trigger a manual fetch.</p>
      </div>
    )
  }

  function handleTabSwitch(tab: "fresh" | "archive") {
    if (tab === activeTab) return
    setFadingOut(true)
    setTimeout(() => {
      setActiveTab(tab)
      setFadingOut(false)
    }, 150)
  }

  function toggleCollapse(id: number) {
    setCollapsedSet((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function handleExpandAll() {
    if (allExpanded) {
      // Re-collapse old articles
      const set = new Set<number>()
      for (const item of archive) {
        if (item.old) set.add(item.article.id)
      }
      setCollapsedSet(set)
    } else {
      setCollapsedSet(new Set())
    }
    setAllExpanded((v) => !v)
  }

  return (
    <>
      {/* Tab bar */}
      {hasArchive && (
        <div className="flex gap-0 mb-4" style={{ borderBottom: "2px solid var(--ink)" }}>
          <button
            onClick={() => handleTabSwitch("fresh")}
            className="cursor-pointer"
            style={{
              fontFamily: "var(--font-sans)", fontSize: "0.9rem", fontWeight: 600,
              padding: "0.5rem 1.4rem", background: "none", border: "none",
              borderBottom: activeTab === "fresh" ? "3px solid var(--accent)" : "3px solid transparent",
              color: activeTab === "fresh" ? "var(--ink)" : "var(--ink-muted)",
              marginBottom: "-2px", transition: "color 0.15s, border-color 0.15s",
            }}
          >
            Fresh <span style={{ fontSize: "0.7rem", fontWeight: 400, color: "var(--ink-muted)", marginLeft: "0.2rem" }}>{fresh.length}</span>
          </button>
          <button
            onClick={() => handleTabSwitch("archive")}
            className="cursor-pointer"
            style={{
              fontFamily: "var(--font-sans)", fontSize: "0.9rem", fontWeight: 600,
              padding: "0.5rem 1.4rem", background: "none", border: "none",
              borderBottom: activeTab === "archive" ? "3px solid var(--accent)" : "3px solid transparent",
              color: activeTab === "archive" ? "var(--ink)" : "var(--ink-muted)",
              marginBottom: "-2px", transition: "color 0.15s, border-color 0.15s",
            }}
          >
            Archive <span style={{ fontSize: "0.7rem", fontWeight: 400, color: "var(--ink-muted)", marginLeft: "0.2rem" }}>{archive.length}</span>
          </button>
        </div>
      )}

      {/* Archive header */}
      {activeTab === "archive" && (
        <div className="flex items-center justify-between mb-3 py-1 gap-2">
          <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.8rem", color: "var(--ink-muted)", fontStyle: "italic" }}>
            Articles older than 7 days. Items over 10 days old are collapsed.
          </p>
          <button
            onClick={handleExpandAll}
            className="cursor-pointer shrink-0"
            style={{
              fontFamily: "var(--font-sans)", fontSize: "0.75rem", padding: "0.2rem 0.6rem",
              border: "1px solid var(--ink)", background: "var(--cream)", color: "var(--ink)",
            }}
          >
            {allExpanded ? "Collapse All" : "Expand All"}
          </button>
        </div>
      )}

      {/* Grid */}
      <div
        className="grid gap-3"
        style={{
          gridTemplateColumns: "repeat(3, 1fr)",
          alignItems: "start",
          opacity: fadingOut ? 0 : 1,
          transition: "opacity 0.15s",
        }}
      >
        {items.map((item) => {
          const focusPosition = visibleIds.indexOf(item.article.id)
          return (
            <ArticleCard
              key={item.article.id}
              article={item.article}
              comments={item.comments}
              isOld={item.old}
              collapsed={collapsedSet.has(item.article.id)}
              onToggleCollapse={() => toggleCollapse(item.article.id)}
              isDismissedView={isDismissedView}
              isBookmarked={bookmarkHas(item.article.id)}
              isFocused={focusPosition === focusIdx}
              onDismiss={onDismiss}
              onRestore={onRestore}
              onBookmark={onBookmark}
              onRemoveSource={onRemoveSource}
            />
          )
        })}
      </div>
    </>
  )
}
