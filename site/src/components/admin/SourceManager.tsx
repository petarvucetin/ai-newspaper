import { useState } from "react"
import type { Source } from "@/types"
import { addSource, toggleSource, deleteSource } from "@/api/client"

interface SourceManagerProps {
  sources: Source[]
  onWeightChange: (id: number, type: "source", weight: number) => void
  onReload: () => void
}

export function SourceManager({ sources, onWeightChange, onReload }: SourceManagerProps) {
  const [name, setName] = useState("")
  const [sourceType, setSourceType] = useState("")
  const [identifier, setIdentifier] = useState("")
  const [weight, setWeight] = useState("1.0")

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    await addSource(name.trim(), sourceType.trim(), identifier.trim(), parseFloat(weight))
    setName("")
    setSourceType("")
    setIdentifier("")
    setWeight("1.0")
    onReload()
  }

  const badgeColors: Record<string, string> = {
    reddit: "var(--reddit-color)",
    youtube: "var(--youtube-color)",
    hackernews: "var(--hn-color)",
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
        Source Weights
      </h3>

      <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.8rem", color: "var(--ink-muted)", marginBottom: "0.5rem" }}>
        HackerNews, YouTube keyword, and other non-channel sources. Use type: <code>hackernews</code>, <code>youtube</code>, or <code>reddit</code>.
      </p>

      <form onSubmit={handleAdd} className="flex gap-2 items-center mb-3 flex-wrap">
        <input type="text" placeholder="Name (e.g. HN: ai agents)" value={name} onChange={(e) => setName(e.target.value)} required className="flex-1 max-w-[300px]" style={{ padding: "0.3rem 0.6rem", border: "1px solid var(--rule)", background: "var(--cream)", fontFamily: "var(--font-sans)", fontSize: "0.85rem" }} />
        <input type="text" placeholder="Type (hackernews / youtube)" value={sourceType} onChange={(e) => setSourceType(e.target.value)} required className="max-w-[150px]" style={{ padding: "0.3rem 0.6rem", border: "1px solid var(--rule)", background: "var(--cream)", fontFamily: "var(--font-sans)", fontSize: "0.85rem" }} />
        <input type="text" placeholder="Identifier / keyword" value={identifier} onChange={(e) => setIdentifier(e.target.value)} required className="flex-1 max-w-[300px]" style={{ padding: "0.3rem 0.6rem", border: "1px solid var(--rule)", background: "var(--cream)", fontFamily: "var(--font-sans)", fontSize: "0.85rem" }} />
        <input type="number" value={weight} onChange={(e) => setWeight(e.target.value)} min={0.1} max={3.0} step={0.05} style={{ width: "80px", padding: "0.2rem 0.4rem", border: "1px solid var(--rule)", background: "var(--cream)", fontFamily: "var(--font-sans)", fontSize: "0.85rem" }} />
        <button type="submit" className="cursor-pointer" style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", padding: "0.2rem 0.6rem", background: "#1a6b2a", border: "1px solid #1a6b2a", color: "#fff" }}>Add Source</button>
      </form>

      <table className="w-full mt-3" style={{ borderCollapse: "collapse", fontFamily: "var(--font-sans)", fontSize: "0.85rem" }}>
        <thead>
          <tr>
            {["Source", "Type", "Weight", "Enabled", "Actions"].map((h) => (
              <th key={h} style={{ background: "var(--ink)", color: "var(--cream)", padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 600 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sources.map((src) => (
            <tr key={src.id}>
              <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>{src.name}</td>
              <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                <span className="inline-block rounded-sm" style={{ fontFamily: "var(--font-sans)", fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", padding: "0.15rem 0.45rem", color: "#fff", background: badgeColors[src.source_type] || "var(--ink-muted)" }}>
                  {src.source_type}
                </span>
              </td>
              <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                <input
                  type="number"
                  defaultValue={src.weight.toFixed(2)}
                  min={0.1} max={3.0} step={0.05}
                  onChange={(e) => onWeightChange(src.id, "source", parseFloat(e.target.value))}
                  style={{ width: "80px", padding: "0.2rem 0.4rem", border: "1px solid var(--rule)", background: "var(--cream)", fontFamily: "var(--font-sans)", fontSize: "0.85rem" }}
                />
              </td>
              <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                <span className="inline-block rounded-full mr-1" style={{ width: "8px", height: "8px", background: src.enabled ? "#2a9d2a" : "#c0392b" }} />
                {src.enabled ? "Yes" : "No"}
              </td>
              <td className="flex gap-1 flex-wrap" style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                <button onClick={async () => { await toggleSource(src.id); onReload() }} className="cursor-pointer" style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", padding: "0.2rem 0.6rem", border: "1px solid var(--ink)", background: "var(--cream)", color: "var(--ink)" }}>
                  {src.enabled ? "Disable" : "Enable"}
                </button>
                <button onClick={async () => { if (confirm(`Delete source ${src.name}?`)) { await deleteSource(src.id); onReload() } }} className="cursor-pointer" style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", padding: "0.2rem 0.6rem", background: "#8b1a1a", border: "1px solid #8b1a1a", color: "#fff" }}>
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
