import { useState } from "react"
import type { KeywordWeight } from "@/types"
import { addKeyword, deleteKeyword } from "@/api/client"

interface KeywordManagerProps {
  keywords: KeywordWeight[]
  onWeightChange: (id: number, type: "keyword", weight: number) => void
  onReload: () => void
}

export function KeywordManager({ keywords, onWeightChange, onReload }: KeywordManagerProps) {
  const [kw, setKw] = useState("")
  const [weight, setWeight] = useState("1.0")

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    await addKeyword(kw.trim(), parseFloat(weight))
    setKw("")
    setWeight("1.0")
    onReload()
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
        Keyword Weights
      </h3>

      <form onSubmit={handleAdd} className="flex gap-2 items-center mb-3">
        <input
          type="text"
          placeholder="New keyword (e.g. agentic rag)"
          value={kw}
          onChange={(e) => setKw(e.target.value)}
          required
          className="flex-1 max-w-[300px]"
          style={{
            padding: "0.3rem 0.6rem", border: "1px solid var(--rule)",
            background: "var(--cream)", fontFamily: "var(--font-sans)", fontSize: "0.85rem",
          }}
        />
        <input
          type="number"
          value={weight}
          onChange={(e) => setWeight(e.target.value)}
          min={0.1} max={5.0} step={0.025}
          style={{
            width: "80px", padding: "0.2rem 0.4rem",
            border: "1px solid var(--rule)", background: "var(--cream)",
            fontFamily: "var(--font-sans)", fontSize: "0.85rem",
          }}
        />
        <button
          type="submit"
          className="cursor-pointer"
          style={{
            fontFamily: "var(--font-sans)", fontSize: "0.75rem",
            padding: "0.2rem 0.6rem", background: "#1a6b2a",
            border: "1px solid #1a6b2a", color: "#fff",
          }}
        >
          Add Keyword
        </button>
      </form>

      <table className="w-full mt-3" style={{ borderCollapse: "collapse", fontFamily: "var(--font-sans)", fontSize: "0.85rem" }}>
        <thead>
          <tr>
            {["Keyword", "Weight", "Hits", "Actions"].map((h) => (
              <th key={h} style={{ background: "var(--ink)", color: "var(--cream)", padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 600 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {keywords.map((kw) => (
            <tr key={kw.id}>
              <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                <code>{kw.keyword}</code>
              </td>
              <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                <input
                  type="number"
                  defaultValue={kw.weight.toFixed(3)}
                  min={0.1} max={5.0} step={0.025}
                  onChange={(e) => onWeightChange(kw.id, "keyword", parseFloat(e.target.value))}
                  style={{
                    width: "80px", padding: "0.2rem 0.4rem",
                    border: "1px solid var(--rule)", background: "var(--cream)",
                    fontFamily: "var(--font-sans)", fontSize: "0.85rem",
                  }}
                />
              </td>
              <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>{kw.hits}</td>
              <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                <button
                  onClick={async () => { if (confirm(`Delete keyword "${kw.keyword}"?`)) { await deleteKeyword(kw.id); onReload() } }}
                  className="cursor-pointer"
                  style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", padding: "0.2rem 0.6rem", background: "#8b1a1a", border: "1px solid #8b1a1a", color: "#fff" }}
                >
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
