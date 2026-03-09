interface SourceBadgeProps {
  sourceType: string
  sourceName: string
}

const COLORS: Record<string, string> = {
  reddit: "var(--reddit-color)",
  youtube: "var(--youtube-color)",
  youtube_channel: "var(--youtube-color)",
  hackernews: "var(--hn-color)",
}

export function SourceBadge({ sourceType, sourceName }: SourceBadgeProps) {
  const bg = COLORS[sourceType] || "var(--ink-muted)"
  let label: string

  if (sourceType === "reddit") {
    label = `r/${sourceName.replace("r/", "")}`
  } else if (sourceType === "youtube" || sourceType === "youtube_channel") {
    label = `\u25B6 ${sourceName.replace("YouTube: ", "")}`
  } else if (sourceType === "hackernews") {
    label = "Y HN"
  } else {
    label = sourceName
  }

  return (
    <span
      className="inline-block rounded-sm whitespace-nowrap"
      style={{
        fontFamily: "var(--font-sans)",
        fontSize: "0.65rem",
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        padding: "0.15rem 0.45rem",
        color: "var(--badge-text)",
        background: bg,
      }}
    >
      {label}
    </span>
  )
}
