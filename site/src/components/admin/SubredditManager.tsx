import { useState } from "react"
import type { Source } from "@/types"
import { addSubreddit, toggleReddit, deleteReddit } from "@/api/client"

interface SubredditManagerProps {
  subreddits: Source[]
  onWeightChange: (id: number, type: "source", weight: number) => void
  onReload: () => void
}

export function SubredditManager({ subreddits, onWeightChange, onReload }: SubredditManagerProps) {
  const [name, setName] = useState("")

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    await addSubreddit(name.trim())
    setName("")
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
        Reddit Subreddits
      </h3>

      <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.8rem", color: "var(--ink-muted)", marginBottom: "0.5rem" }}>
        Active subreddits are fetched each run. Disable to pause without deleting.
      </p>

      <form onSubmit={handleAdd} className="flex gap-2 items-center mb-3">
        <input
          type="text"
          placeholder="r/MachineLearning or MachineLearning"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="flex-1 max-w-[300px]"
          style={{
            padding: "0.3rem 0.6rem", border: "1px solid var(--rule)",
            background: "var(--cream)", fontFamily: "var(--font-sans)", fontSize: "0.85rem",
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
          Add Subreddit
        </button>
      </form>

      {subreddits.length > 0 ? (
        <table className="w-full mt-3" style={{ borderCollapse: "collapse", fontFamily: "var(--font-sans)", fontSize: "0.85rem" }}>
          <thead>
            <tr>
              {["Subreddit", "Status", "Weight", "Actions"].map((h) => (
                <th key={h} style={{ background: "var(--ink)", color: "var(--cream)", padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {subreddits.map((r) => (
              <tr key={r.id}>
                <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                  <a href={`https://www.reddit.com/r/${r.identifier}`} target="_blank" rel="noopener" style={{ color: "var(--ink)" }}>
                    r/{r.identifier}
                  </a>
                </td>
                <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                  <span
                    className="inline-block rounded-full mr-1"
                    style={{ width: "8px", height: "8px", background: r.enabled ? "#2a9d2a" : "#c0392b" }}
                  />
                  {r.enabled ? "Active" : "Disabled"}
                </td>
                <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                  <input
                    type="number"
                    defaultValue={r.weight.toFixed(2)}
                    min={0.1}
                    max={3.0}
                    step={0.05}
                    onChange={(e) => onWeightChange(r.id, "source", parseFloat(e.target.value))}
                    style={{
                      width: "80px", padding: "0.2rem 0.4rem",
                      border: "1px solid var(--rule)", background: "var(--cream)",
                      fontFamily: "var(--font-sans)", fontSize: "0.85rem",
                    }}
                  />
                </td>
                <td className="flex gap-1 flex-wrap" style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                  <button
                    onClick={async () => { await toggleReddit(r.id); onReload() }}
                    className="cursor-pointer"
                    style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", padding: "0.2rem 0.6rem", border: "1px solid var(--ink)", background: "var(--cream)", color: "var(--ink)" }}
                  >
                    {r.enabled ? "Disable" : "Enable"}
                  </button>
                  <button
                    onClick={async () => { if (confirm(`Remove r/${r.identifier} from the list?`)) { await deleteReddit(r.id); onReload() } }}
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
      ) : (
        <p className="mt-2" style={{ fontFamily: "var(--font-sans)", fontSize: "0.85rem", color: "var(--ink-muted)", fontStyle: "italic" }}>
          No subreddits yet.
        </p>
      )}
    </section>
  )
}
