import { useEffect, useRef } from "react"
import type { Article, Comment } from "@/types"
import { SourceBadge } from "./SourceBadge"
import { StarRating } from "./StarRating"

interface ArticleCardProps {
  article: Article
  comments?: Comment[]
  isOld: boolean
  collapsed: boolean
  onToggleCollapse?: () => void
  isDismissedView: boolean
  isBookmarked: boolean
  isFocused: boolean
  onDismiss: (id: number) => void
  onRestore: (id: number) => void
  onBookmark: (id: number) => void
  onRemoveSource: (sourceId: number, sourceName: string) => void
}

function fmtCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function fmtPubTime(utcStr: string): string {
  const dt = new Date(utcStr.replace(" ", "T") + "Z")
  const now = new Date()
  const diffMs = now.getTime() - dt.getTime()
  const diffH = diffMs / 3_600_000
  if (diffH < 1) return `${Math.round(diffMs / 60_000)}m ago`
  if (diffH < 24) return `${Math.round(diffH)}h ago`
  if (diffH < 48) return `Yesterday ${dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
  return `${dt.toLocaleDateString([], { month: "short", day: "numeric" })} ${dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
}

function fmtTooltip(utcStr: string): string {
  const dt = new Date(utcStr.replace(" ", "T") + "Z")
  return dt.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })
}

function relevancyClass(score: number): string {
  const pct = Math.min(Math.round(score * 100), 100)
  if (pct >= 70) return "var(--score-high)"
  if (pct >= 40) return "var(--score-mid)"
  return "var(--score-low)"
}

export function ArticleCard({
  article, comments, isOld, collapsed, onToggleCollapse,
  isDismissedView, isBookmarked, isFocused,
  onDismiss, onRestore, onBookmark, onRemoveSource,
}: ArticleCardProps) {
  const cardRef = useRef<HTMLElement>(null)
  const rscore = article.relevancy_score || 0
  const rpct = Math.min(Math.round(rscore * 100), 100)
  const isYoutube = article.source_type === "youtube" || article.source_type === "youtube_channel"

  useEffect(() => {
    if (isFocused && cardRef.current) {
      cardRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" })
    }
  }, [isFocused])

  return (
    <article
      ref={cardRef}
      data-article-id={article.id}
      data-source-id={article.source_id}
      className="flex flex-col overflow-hidden rounded-md"
      style={{
        background: isBookmarked ? "color-mix(in srgb, var(--cream) 92%, var(--star-on) 8%)" : "var(--cream)",
        border: "1px solid var(--rule)",
        borderLeft: `3px solid ${relevancyClass(rscore)}`,
        height: collapsed ? "auto" : "380px",
        maxHeight: collapsed ? "56px" : undefined,
        opacity: collapsed ? 0.75 : 1,
        transition: "box-shadow 0.2s, transform 0.2s, max-height 0.25s ease",
        boxShadow: isFocused ? "0 2px 12px rgba(0,0,0,0.08), inset 0 -3px 0 var(--accent)" : undefined,
      }}
      title={`Relevancy: ${rpct}%`}
    >
      {/* Thumbnail */}
      {isYoutube && article.thumbnail_url && !collapsed && (
        <img
          src={article.thumbnail_url}
          alt=""
          loading="lazy"
          className="w-full block"
          style={{ aspectRatio: "16/9", maxHeight: "160px", objectFit: "cover", borderBottom: "1px solid var(--rule)" }}
        />
      )}

      <div className="flex flex-col gap-1.5 flex-1 min-h-0 overflow-hidden" style={{ padding: "0.8rem 1rem" }}>
        {/* Meta top row */}
        <div className="flex items-center gap-2 flex-wrap shrink-0" style={{ flexWrap: collapsed ? "nowrap" : "wrap" }}>
          <SourceBadge sourceType={article.source_type} sourceName={article.source_name} />

          {rscore > 0 && (
            <span
              className="whitespace-nowrap rounded-sm"
              style={{
                fontFamily: "var(--font-sans)", fontSize: "0.62rem", fontWeight: 600,
                color: rpct >= 70 ? "var(--score-high)" : rpct >= 40 ? "var(--score-mid)" : "var(--ink-muted)",
                background: "var(--cream-dark)", padding: "0.1rem 0.35rem",
              }}
              title={`Relevancy: ${rscore.toFixed(2)}`}
            >
              {rpct}%
            </span>
          )}

          {article.auto_dismissed === 1 && (
            <span
              className="rounded-sm"
              style={{
                fontFamily: "var(--font-sans)", fontSize: "0.6rem", fontWeight: 700,
                textTransform: "uppercase", letterSpacing: "0.04em",
                color: "var(--ink-muted)", background: "var(--cream-dark)",
                border: "1px solid var(--rule)", padding: "0.1rem 0.35rem",
              }}
              title="Auto-dismissed by classifier"
            >
              Auto
            </span>
          )}

          {article.published_at && (
            <span
              className="ml-auto cursor-default"
              style={{ fontFamily: "var(--font-sans)", fontSize: "0.7rem", color: "var(--ink-muted)" }}
              title={fmtTooltip(article.published_at)}
            >
              {fmtPubTime(article.published_at)}
            </span>
          )}

          {isOld && (
            <button
              onClick={(e) => { e.stopPropagation(); onToggleCollapse?.() }}
              title={collapsed ? "Expand article" : "Collapse article"}
              className="cursor-pointer ml-auto"
              style={{ background: "none", border: "none", color: "var(--ink-muted)", fontSize: "0.65rem", padding: "0.1rem 0.3rem", lineHeight: 1, transition: "color 0.15s" }}
            >
              {collapsed ? "\u25BC" : "\u25B2"}
            </button>
          )}
        </div>

        {/* Metrics row */}
        {!collapsed && (
          <div className="flex gap-2.5" style={{ fontFamily: "var(--font-sans)", fontSize: "0.72rem", color: "var(--ink-muted)" }}>
            {isYoutube ? (
              article.upvotes > 0 && (
                <span style={{ fontWeight: 600, color: "var(--youtube-color)" }}>
                  &#128065; {fmtCount(article.upvotes)} views
                </span>
              )
            ) : (
              <>
                {article.upvotes > 0 && <span>&#9650; {fmtCount(article.upvotes)}</span>}
                {article.source_type === "reddit" && article.num_comments > 0 && (
                  <span>&#128172; {fmtCount(article.num_comments)}</span>
                )}
              </>
            )}
          </div>
        )}

        {/* Scrollable body */}
        {!collapsed && (
          <div className="flex-1 overflow-y-auto flex flex-col gap-1.5">
            <h2
              className="article-title"
              style={{ fontFamily: "var(--font-serif)", fontSize: "var(--article-font-size)", fontWeight: 700, lineHeight: 1.3, color: "var(--ink)" }}
            >
              <a
                href={article.url}
                target="_blank"
                rel="noopener"
                style={{ color: "inherit", textDecoration: "none" }}
                onMouseEnter={(e) => (e.currentTarget.style.textDecoration = "underline")}
                onMouseLeave={(e) => (e.currentTarget.style.textDecoration = "none")}
              >
                {article.title}
              </a>
            </h2>

            {article.summary && (
              <div style={{ fontSize: "calc(var(--article-font-size) * 0.85)", color: "var(--ink-light)" }}>
                {article.summary.split("\n\n").filter(Boolean).map((para, i) => (
                  <p key={i} style={{ marginBottom: "0.4rem" }}>{para.trim()}</p>
                ))}
              </div>
            )}

            {comments && comments.length > 0 && (
              <div style={{ marginTop: "0.6rem", paddingTop: "0.5rem", borderTop: "1px dashed var(--rule)" }}>
                <span
                  className="block"
                  style={{
                    fontFamily: "var(--font-sans)", fontSize: "0.7rem", fontWeight: 700,
                    textTransform: "uppercase", letterSpacing: "0.05em",
                    color: "var(--ink-muted)", marginBottom: "0.35rem",
                  }}
                >
                  Top comments
                </span>
                {comments.slice(0, 3).map((c, i) => (
                  <div key={i} style={{ fontSize: "calc(var(--article-font-size) * 0.78)", color: "var(--ink-light)", marginBottom: "0.3rem", lineHeight: 1.35 }}>
                    <span style={{ fontStyle: "italic" }}>{c.body}</span>
                    <span style={{ fontSize: "0.75em", color: "var(--ink-muted)", whiteSpace: "nowrap" }}>
                      {" "}&mdash; {c.author}
                      {c.comment_url && (
                        <>{" "}<a href={c.comment_url} target="_blank" rel="noopener" style={{ color: "var(--accent)", textDecoration: "none", fontSize: "0.85em" }} title="View comment">&#8599;</a></>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Footer — pinned at bottom */}
        {!collapsed && (
          <div
            className="flex items-center justify-between shrink-0 flex-wrap gap-2"
            style={{ marginTop: "auto", paddingTop: "0.5rem", borderTop: "1px solid var(--rule)" }}
          >
            <div className="flex items-center gap-2">
              <StarRating articleId={article.id} userRating={article.user_rating} />

              <button
                onClick={() => onBookmark(article.id)}
                title="Bookmark"
                className="cursor-pointer"
                style={{
                  background: "none", border: "none", fontSize: "0.9rem",
                  color: isBookmarked ? "var(--star-on)" : "var(--ink-muted)",
                  padding: "0.1rem 0.2rem", lineHeight: 1, transition: "color 0.15s, transform 0.15s",
                }}
              >
                {isBookmarked ? "\u2605" : "\u2606"}
              </button>

              {isDismissedView ? (
                <button
                  onClick={() => onRestore(article.id)}
                  title="Restore article"
                  className="cursor-pointer rounded-sm"
                  style={{ background: "none", border: "none", color: "var(--ink-muted)", fontSize: "0.85rem", padding: "0.2rem 0.35rem", lineHeight: 1, transition: "color 0.15s" }}
                >
                  &#8617;
                </button>
              ) : (
                <button
                  onClick={() => onDismiss(article.id)}
                  title="Dismiss article"
                  className="cursor-pointer rounded-sm"
                  style={{ background: "none", border: "none", color: "var(--ink-muted)", fontSize: "0.75rem", padding: "0.2rem 0.35rem", lineHeight: 1, transition: "color 0.15s" }}
                >
                  &#10005;
                </button>
              )}

              {["reddit", "youtube_channel", "youtube"].includes(article.source_type) && (
                <button
                  onClick={() => onRemoveSource(article.source_id, article.source_name)}
                  title={`Remove source: ${article.source_name}`}
                  className="cursor-pointer rounded-sm"
                  style={{ background: "none", border: "none", color: "var(--ink-muted)", fontSize: "0.75rem", padding: "0.2rem 0.35rem", lineHeight: 1, transition: "color 0.15s" }}
                >
                  &#128683;
                </button>
              )}
            </div>

            {article.author && (
              <span
                style={{
                  fontFamily: "var(--font-sans)", fontSize: "0.65rem", color: "var(--ink-muted)",
                  maxWidth: "120px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}
                title={article.author}
              >
                {article.author}
              </span>
            )}
          </div>
        )}
      </div>
    </article>
  )
}
