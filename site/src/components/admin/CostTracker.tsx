import type { ApiUsageSummary } from "@/types"

interface CostTrackerProps {
  usage: ApiUsageSummary
}

export function CostTracker({ usage }: CostTrackerProps) {
  const o = usage.overall

  return (
    <section className="mb-10">
      <h3
        style={{
          fontSize: "1.1rem", fontWeight: 700, textTransform: "uppercase",
          letterSpacing: "0.08em", color: "var(--accent)",
          borderBottom: "1px solid var(--rule)", paddingBottom: "0.3rem", marginBottom: "0.75rem",
        }}
      >
        API Cost (last 30 days)
      </h3>

      <div className="flex items-baseline gap-4 flex-wrap">
        <div style={{ fontFamily: "var(--font-serif)", fontSize: "2rem", fontWeight: 700, color: "var(--ink)" }}>
          ${(o.total_cost || 0).toFixed(4)}
        </div>
        <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.8rem", color: "var(--ink-muted)" }}>
          {(o.total_input || 0).toLocaleString()} input tokens &nbsp;&middot;&nbsp;
          {(o.total_output || 0).toLocaleString()} output tokens &nbsp;&middot;&nbsp;
          {o.total_calls || 0} calls
        </div>
      </div>

      {usage.totals.length > 0 && (
        <>
          <table
            className="w-full mt-3"
            style={{ borderCollapse: "collapse", fontFamily: "var(--font-sans)", fontSize: "0.85rem" }}
          >
            <thead>
              <tr>
                {["Purpose", "Calls", "Input tok", "Output tok", "Cost"].map((h) => (
                  <th
                    key={h}
                    style={{
                      background: "var(--ink)", color: "var(--cream)",
                      padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 600,
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {usage.totals.map((row, i) => (
                <tr key={i}>
                  <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>{row.purpose || row.model}</td>
                  <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>{row.calls}</td>
                  <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>{row.input_tokens.toLocaleString()}</td>
                  <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>{row.output_tokens.toLocaleString()}</td>
                  <td style={{ padding: "0.45rem 0.75rem", borderBottom: "1px solid var(--rule)" }}>${row.cost_usd.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {usage.daily.length > 0 && (
            <p className="mt-3" style={{ fontFamily: "var(--font-sans)", fontSize: "0.8rem", color: "var(--ink-muted)" }}>
              Last 7 days:{" "}
              {usage.daily.map((d, i) => (
                <span key={d.day}>
                  <strong>{d.day}</strong> ${d.cost_usd.toFixed(4)}
                  {i < usage.daily.length - 1 && " \u00B7 "}
                </span>
              ))}
            </p>
          )}
        </>
      )}

      {usage.totals.length === 0 && (
        <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.85rem", color: "var(--ink-muted)", fontStyle: "italic" }}>
          No API calls recorded yet.
        </p>
      )}
    </section>
  )
}
