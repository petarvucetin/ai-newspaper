import { useState } from "react"
import type { Source } from "@/types"
import { addChannel, pinChannel, unpinChannel, deleteChannel } from "@/api/client"

interface ChannelManagerProps {
  channels: Source[]
  onWeightChange: (id: number, type: "source", weight: number) => void
  onReload: () => void
}

export function ChannelManager({ channels, onWeightChange, onReload }: ChannelManagerProps) {
  const [handle, setHandle] = useState("")

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!handle.trim()) return
    await addChannel(handle.trim())
    setHandle("")
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
        YouTube Channels
      </h3>

      <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.8rem", color: "var(--ink-muted)", marginBottom: "0.5rem" }}>
        Pinned channels are fetched directly. Discovered channels appear here after keyword searches — pin them to subscribe.
      </p>

      <form onSubmit={handleAdd} className="flex gap-2 items-center mb-3">
        <input
          type="text"
          placeholder="@ChannelHandle"
          value={handle}
          onChange={(e) => setHandle(e.target.value)}
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
          Add Channel
        </button>
      </form>

      {channels.length > 0 ? (
        <table className="w-full" style={{ borderCollapse: "collapse", fontFamily: "var(--font-sans)", fontSize: "0.85rem" }}>
          <thead>
            <tr>
              {["Channel", "Status", "Weight", "Actions"].map((h) => (
                <th key={h} style={{ background: "var(--ink)", color: "var(--cream)", padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {channels.map((ch) => (
              <tr key={ch.id}>
                <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                  <a href={`https://www.youtube.com/${ch.identifier}`} target="_blank" rel="noopener" style={{ color: "var(--ink)" }}>{ch.name}</a>
                  <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.7rem", color: "var(--ink-muted)", marginLeft: "0.4rem" }}>{ch.identifier}</span>
                </td>
                <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                  <span
                    className="inline-block rounded-full"
                    style={{
                      fontFamily: "var(--font-sans)", fontSize: "0.65rem", fontWeight: 700,
                      textTransform: "uppercase", letterSpacing: "0.05em",
                      padding: "0.15rem 0.5rem", color: "#fff",
                      background: ch.enabled ? "#1a6b2a" : "#7a5c00",
                    }}
                  >
                    {ch.enabled ? "Pinned" : "Discovered"}
                  </span>
                </td>
                <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                  <input
                    type="number"
                    defaultValue={ch.weight.toFixed(2)}
                    min={0.1}
                    max={3.0}
                    step={0.05}
                    onChange={(e) => onWeightChange(ch.id, "source", parseFloat(e.target.value))}
                    style={{
                      width: "80px", padding: "0.2rem 0.4rem",
                      border: "1px solid var(--rule)", background: "var(--cream)",
                      fontFamily: "var(--font-sans)", fontSize: "0.85rem",
                    }}
                  />
                </td>
                <td className="flex gap-1 flex-wrap" style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>
                  {ch.enabled ? (
                    <button
                      onClick={async () => { await unpinChannel(ch.id); onReload() }}
                      className="cursor-pointer"
                      style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", padding: "0.2rem 0.6rem", border: "1px solid var(--ink)", background: "var(--cream)", color: "var(--ink)" }}
                    >
                      Unpin
                    </button>
                  ) : (
                    <button
                      onClick={async () => { await pinChannel(ch.id); onReload() }}
                      className="cursor-pointer"
                      style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", padding: "0.2rem 0.6rem", background: "#1a6b2a", border: "1px solid #1a6b2a", color: "#fff" }}
                    >
                      Pin
                    </button>
                  )}
                  <button
                    onClick={async () => { if (confirm(`Remove ${ch.name} from the list?`)) { await deleteChannel(ch.id); onReload() } }}
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
        <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.85rem", color: "var(--ink-muted)", fontStyle: "italic" }}>
          No channels yet. Run a fetch to discover channels via keyword search.
        </p>
      )}
    </section>
  )
}
