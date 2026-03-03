import { useState, useMemo, type ReactNode } from "react"
import { Link, useSearchParams, useNavigate } from "react-router-dom"
import { useTheme } from "@/hooks/useTheme"
import { useFontSize } from "@/hooks/useFontSize"
import { ExpandableTabs } from "@/components/ui/expandable-tabs"
import { Layers, MessageCircle, Play, Flame, Bookmark, EyeOff } from "lucide-react"

const FILTER_TABS = [
  { key: "all", title: "All", icon: Layers },
  { key: "reddit", title: "Reddit", icon: MessageCircle },
  { key: "youtube", title: "YouTube", icon: Play },
  { key: "hackernews", title: "Hacker News", icon: Flame },
  { type: "separator" as const },
  { key: "bookmarks", title: "Bookmarks", icon: Bookmark },
  { key: "dismissed", title: "Dismissed", icon: EyeOff },
] as const

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
  const navigate = useNavigate()
  const activeFilter = searchParams.get("source") || "all"

  const lastFetchedStr = lastFetchedUtc
    ? new Date(lastFetchedUtc.replace(" ", "T") + "Z").toLocaleString([], {
        weekday: "long", year: "numeric", month: "long",
        day: "numeric", hour: "2-digit", minute: "2-digit",
      })
    : ""

  // Build tabs for ExpandableTabs — map filter keys to tab entries
  const filterTabs = useMemo(() =>
    FILTER_TABS.map((t) => {
      if ("type" in t && t.type === "separator") return { type: "separator" as const }
      const count = sourceCounts?.[t.key]
      const showCount = count != null && t.key !== "all" && t.key !== "bookmarks" && t.key !== "dismissed"
      return {
        title: showCount ? `${t.title} (${count})` : t.title,
        icon: t.icon,
      }
    }), [sourceCounts])

  // Find active tab index from URL
  const activeTabIndex = useMemo(() => {
    const nonSepTabs = FILTER_TABS.filter((t) => !("type" in t && t.type === "separator"))
    const idx = nonSepTabs.findIndex((t) => t.key === activeFilter)
    if (idx === -1) return 0
    // Account for separators when mapping to the full array index
    let realIdx = 0
    let count = 0
    for (const t of FILTER_TABS) {
      if ("type" in t && t.type === "separator") { realIdx++; continue }
      if (count === idx) return realIdx
      count++
      realIdx++
    }
    return 0
  }, [activeFilter])

  const handleTabChange = (index: number | null) => {
    if (index === null) return
    // Map tab index back to filter key (skip separators)
    const tab = FILTER_TABS[index]
    if (tab && "key" in tab) {
      navigate(`/?source=${tab.key}`)
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Masthead */}
      <header
        className="sticky top-0 z-50 border-b-[3px] border-double"
        style={{
          background: "color-mix(in srgb, var(--cream) 85%, transparent)",
          backdropFilter: "blur(8px)",
          WebkitBackdropFilter: "blur(8px)",
          borderColor: "var(--ink)",
        }}
      >
        <div className="max-w-[1400px] mx-auto w-full px-6 md:px-10 lg:px-16 pt-4 pb-1">
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
            <div className="flex items-center gap-3 min-w-[120px] justify-end" style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem" }}>
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

          {/* Filter nav — Expandable Tabs */}
          {showFilters && (
            <nav className="py-3">
              <ExpandableTabs
                tabs={filterTabs}
                activeIndex={activeTabIndex}
                onChange={handleTabChange}
              />
            </nav>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-[1400px] mx-auto w-full px-6 md:px-10 lg:px-16 py-6">
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
