import { useState, useEffect, useCallback, useRef } from "react"
import { Layout } from "@/components/Layout"
import { FetchControl } from "@/components/admin/FetchControl"
import { CostTracker } from "@/components/admin/CostTracker"
import { ChannelManager } from "@/components/admin/ChannelManager"
import { SubredditManager } from "@/components/admin/SubredditManager"
import { SourceManager } from "@/components/admin/SourceManager"
import { KeywordManager } from "@/components/admin/KeywordManager"
import { fetchAdminData, saveWeights, uploadCookies, deleteCookies } from "@/api/client"
import type { AdminData, CookiesStatus } from "@/types"

export function AdminPage() {
  const [data, setData] = useState<AdminData | null>(null)
  const [loading, setLoading] = useState(true)

  // Dirty weight tracking
  const originalsRef = useRef<Map<string, number>>(new Map())
  const [dirtyWeights, setDirtyWeights] = useState<Map<string, { id: number; type: "source" | "keyword"; weight: number }>>(new Map())
  const [saveStatus, setSaveStatus] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await fetchAdminData()
      setData(resp)
      // Reset dirty tracking
      originalsRef.current.clear()
      setDirtyWeights(new Map())
    } catch (err) {
      console.error("Failed to load admin data:", err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  function handleWeightChange(id: number, type: "source" | "keyword", weight: number) {
    const key = `${type}-${id}`
    if (!originalsRef.current.has(key)) {
      // Record original
      const original = type === "source"
        ? [...(data?.sources || []), ...(data?.channels || []), ...(data?.reddit_sources || [])].find((s) => s.id === id)?.weight
        : data?.keywords.find((k) => k.id === id)?.weight
      if (original !== undefined) originalsRef.current.set(key, original)
    }

    setDirtyWeights((prev) => {
      const next = new Map(prev)
      const original = originalsRef.current.get(key)
      if (original !== undefined && Math.abs(weight - original) < 0.001) {
        next.delete(key)
      } else {
        next.set(key, { id, type, weight })
      }
      return next
    })
  }

  async function handleSaveAll() {
    const sources: { id: number; weight: number }[] = []
    const keywords: { id: number; weight: number }[] = []
    for (const entry of dirtyWeights.values()) {
      if (entry.type === "source") sources.push({ id: entry.id, weight: entry.weight })
      else keywords.push({ id: entry.id, weight: entry.weight })
    }

    setSaveStatus("Saving\u2026")
    try {
      const resp = await saveWeights(sources, keywords)
      if (resp.ok) {
        setSaveStatus(`\u2713 Saved ${resp.updated} weight${resp.updated > 1 ? "s" : ""}`)
        // Clear dirty
        originalsRef.current.clear()
        setDirtyWeights(new Map())
        setTimeout(() => setSaveStatus(null), 1500)
      } else {
        setSaveStatus("Save failed")
      }
    } catch {
      setSaveStatus("Save failed \u2014 network error")
    }
  }

  async function handleUploadCookies(file: File) {
    await uploadCookies(file)
    load()
  }

  async function handleDeleteCookies() {
    if (confirm("Remove the cookies file?")) {
      await deleteCookies()
      load()
    }
  }

  if (loading && !data) {
    return (
      <Layout showFilters>
        <div className="text-center py-16" style={{ color: "var(--ink-muted)" }}>Loading...</div>
      </Layout>
    )
  }

  if (!data) {
    return (
      <Layout showFilters>
        <div className="text-center py-16" style={{ color: "var(--accent)" }}>Failed to load admin data.</div>
      </Layout>
    )
  }

  return (
    <Layout showFilters>
      <div className="max-w-[960px] mx-auto" style={{ padding: "1.5rem", paddingBottom: "4rem" }}>
        <h2
          style={{
            fontSize: "1.5rem", fontWeight: 700,
            borderBottom: "2px solid var(--ink)", paddingBottom: "0.5rem", marginBottom: "1.5rem",
          }}
        >
          Admin Dashboard
        </h2>

        <FetchControl scheduleTime={data.schedule_time} autoEnabled={data.auto_enabled} />
        <CostTracker usage={data.api_usage} />

        {/* YouTube Cookies */}
        <CookiesSection cookies={data.cookies_status} onUpload={handleUploadCookies} onDelete={handleDeleteCookies} />

        <ChannelManager channels={data.channels} onWeightChange={handleWeightChange} onReload={load} />
        <SubredditManager subreddits={data.reddit_sources} onWeightChange={handleWeightChange} onReload={load} />
        <SourceManager sources={data.sources} onWeightChange={handleWeightChange} onReload={load} />
        <KeywordManager keywords={data.keywords} onWeightChange={handleWeightChange} onReload={load} />

        {/* Save bar */}
        {(dirtyWeights.size > 0 || saveStatus) && (
          <div
            className="fixed bottom-0 left-0 right-0 flex items-center justify-center gap-4 z-50"
            style={{
              background: "var(--ink)", color: "var(--cream)",
              padding: "0.65rem 1.5rem", boxShadow: "0 -2px 8px rgba(0,0,0,0.15)",
            }}
          >
            <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.9rem" }}>
              {saveStatus || `${dirtyWeights.size} unsaved change${dirtyWeights.size > 1 ? "s" : ""}`}
            </span>
            {!saveStatus && (
              <button
                onClick={handleSaveAll}
                className="cursor-pointer"
                style={{
                  fontFamily: "var(--font-sans)", fontSize: "0.85rem", fontWeight: 700,
                  padding: "0.4rem 1rem", background: "var(--accent)",
                  border: "1px solid var(--accent)", color: "var(--cream)",
                }}
              >
                Save All
              </button>
            )}
          </div>
        )}
      </div>
    </Layout>
  )
}

// --- Cookies sub-section ---
function CookiesSection({ cookies, onUpload, onDelete }: {
  cookies: CookiesStatus
  onUpload: (file: File) => void
  onDelete: () => void
}) {
  function handleFileSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const input = e.currentTarget.querySelector("input[type=file]") as HTMLInputElement
    if (input.files?.[0]) onUpload(input.files[0])
  }

  const alertStyle: React.CSSProperties = cookies.exists
    ? cookies.warning
      ? { background: "#fff3cd", color: "#664d03" }
      : { background: "#d1e7dd", color: "#0a4a26" }
    : { background: "#f8d7da", color: "#58151c" }

  return (
    <section className="mb-10">
      <h3
        style={{
          fontSize: "1.1rem", fontWeight: 700, textTransform: "uppercase",
          letterSpacing: "0.08em", color: "var(--accent)",
          borderBottom: "1px solid var(--rule)", paddingBottom: "0.3rem", marginBottom: "0.75rem",
        }}
      >
        YouTube Cookies
      </h3>

      <div
        className="rounded-sm mb-3"
        style={{ fontFamily: "var(--font-sans)", fontSize: "0.85rem", padding: "0.5rem 0.9rem", ...alertStyle }}
      >
        {!cookies.exists && <><strong>No cookies file found.</strong> YouTube will block transcript and video fetches.</>}
        {cookies.exists && cookies.warning && <><strong>Cookies are {cookies.age_days} days old</strong> and may have expired.</>}
        {cookies.exists && !cookies.warning && <>Cookies file present &mdash; {cookies.age_days} day{cookies.age_days !== 1 ? "s" : ""} old.</>}
      </div>

      <form onSubmit={handleFileSubmit} className="flex gap-2 items-center mt-3">
        <input type="file" accept=".txt,text/plain" required style={{ fontFamily: "var(--font-sans)", fontSize: "0.85rem" }} />
        <button type="submit" className="cursor-pointer" style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", padding: "0.2rem 0.6rem", background: "#1a6b2a", border: "1px solid #1a6b2a", color: "#fff" }}>
          Upload Cookies
        </button>
      </form>

      {cookies.exists && (
        <button
          onClick={onDelete}
          className="cursor-pointer mt-2"
          style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", padding: "0.2rem 0.6rem", background: "#8b1a1a", border: "1px solid #8b1a1a", color: "#fff" }}
        >
          Remove Cookies
        </button>
      )}
    </section>
  )
}
