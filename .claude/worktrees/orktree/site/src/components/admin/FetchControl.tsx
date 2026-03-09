import { useState, useEffect, useRef, useCallback } from "react"
import { startFetch, fetchFetchStatus, saveSchedule } from "@/api/client"
import type { FetchStatus } from "@/types"

interface FetchControlProps {
  scheduleTime: string
  autoEnabled: boolean
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

export function FetchControl({ scheduleTime: initTime, autoEnabled: initAuto }: FetchControlProps) {
  const [running, setRunning] = useState(false)
  const [badge, setBadge] = useState<{ cls: string; text: string }>({ cls: "", text: "" })
  const [logLines, setLogLines] = useState<string[]>([])
  const [showProgress, setShowProgress] = useState(false)
  const [scheduleTime, setScheduleTime] = useState(initTime)
  const [autoEnabled, setAutoEnabled] = useState(initAuto)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const logRef = useRef<HTMLDivElement>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  useEffect(() => () => stopPolling(), [stopPolling])

  async function handleFetch() {
    setRunning(true)
    setBadge({ cls: "badge-running", text: "Starting\u2026" })
    setLogLines([])
    setShowProgress(true)

    try {
      const data = await startFetch()
      if (data.status === "already_running") {
        setBadge({ cls: "badge-running", text: "Already running\u2026" })
      }
    } catch {
      setBadge({ cls: "badge-error", text: "Failed to start" })
      setRunning(false)
      return
    }

    pollRef.current = setInterval(async () => {
      try {
        const data: FetchStatus = await fetchFetchStatus()
        setLogLines(data.log)
        if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight

        if (data.status === "done") {
          stopPolling()
          setRunning(false)
          setBadge({ cls: "badge-done", text: `\u2713 ${data.inserted} new, ${data.skipped} skipped \u2014 ${data.elapsed}s` })
        } else if (data.status === "error") {
          stopPolling()
          setRunning(false)
          setBadge({ cls: "badge-error", text: `\u2717 ${data.error}` })
        } else {
          setBadge({ cls: "badge-running", text: "Running\u2026" })
        }
      } catch {
        /* network hiccup, keep polling */
      }
    }, 1000)
  }

  async function handleSaveSchedule(e: React.FormEvent) {
    e.preventDefault()
    await saveSchedule(scheduleTime, autoEnabled)
  }

  const badgeStyle: Record<string, React.CSSProperties> = {
    "badge-running": { background: "#fef3cd", color: "#856404", animation: "pulse 1.2s ease-in-out infinite" },
    "badge-done": { background: "#d1e7dd", color: "#0a4a26" },
    "badge-error": { background: "#f8d7da", color: "#6b1c22" },
  }

  return (
    <section className="mb-10">
      <h3
        style={{
          fontSize: "1.1rem", fontWeight: 700, textTransform: "uppercase",
          letterSpacing: "0.08em", color: "var(--accent)",
          borderBottom: "1px solid var(--rule)", paddingBottom: "0.3rem", marginBottom: "0.75rem",
        }}
      >
        Fetch
      </h3>

      <div className="flex items-center gap-4">
        <button
          onClick={handleFetch}
          disabled={running}
          className="cursor-pointer"
          style={{
            fontFamily: "var(--font-sans)", fontSize: "0.85rem", fontWeight: 700,
            padding: "0.5rem 1.5rem", background: "var(--accent)",
            border: "1px solid var(--accent)", color: "var(--cream)",
            opacity: running ? 0.6 : 1,
          }}
        >
          Fetch Now
        </button>
        {badge.text && (
          <span
            className="rounded-sm"
            style={{
              fontFamily: "var(--font-sans)", fontSize: "0.8rem", fontWeight: 600,
              padding: "0.2rem 0.6rem",
              ...(badgeStyle[badge.cls] || {}),
            }}
          >
            {badge.text}
          </span>
        )}
      </div>

      {showProgress && (
        <div className="mt-4 rounded-sm overflow-hidden" style={{ border: "1px solid var(--rule)" }}>
          <div
            ref={logRef}
            style={{
              background: "#1a1a1a", color: "#d4d4d4",
              fontFamily: "'Courier New', monospace", fontSize: "0.78rem",
              padding: "0.75rem 1rem", maxHeight: "220px", overflowY: "auto", lineHeight: 1.7,
            }}
          >
            {logLines.map((line, i) => (
              <div
                key={i}
                style={{ whiteSpace: "pre-wrap", color: i === logLines.length - 1 ? "#fff" : undefined }}
                dangerouslySetInnerHTML={{ __html: escHtml(line) }}
              />
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSaveSchedule} className="flex items-center gap-2.5 mt-3 flex-wrap">
        <label className="flex items-center gap-1.5 cursor-pointer" style={{ fontFamily: "var(--font-sans)", fontSize: "0.85rem" }}>
          <input
            type="checkbox"
            checked={autoEnabled}
            onChange={(e) => setAutoEnabled(e.target.checked)}
          />
          Auto-fetch daily at
        </label>
        <input
          type="time"
          value={scheduleTime}
          onChange={(e) => setScheduleTime(e.target.value)}
          required
          style={{
            padding: "0.2rem 0.4rem", border: "1px solid var(--rule)",
            background: "var(--cream)", fontFamily: "var(--font-sans)", fontSize: "0.85rem",
          }}
        />
        <button
          type="submit"
          className="cursor-pointer"
          style={{
            fontFamily: "var(--font-sans)", fontSize: "0.75rem",
            padding: "0.2rem 0.6rem", border: "1px solid var(--ink)",
            background: "var(--ink)", color: "var(--cream)",
          }}
        >
          Save Schedule
        </button>
        <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.78rem", color: "var(--ink-muted)" }}>
          {autoEnabled ? "Enabled" : "Disabled"}
        </span>
      </form>

      <style>{`@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }`}</style>
    </section>
  )
}
