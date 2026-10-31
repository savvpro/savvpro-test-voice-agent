import type { TurnResponse } from "@/lib/types";

const SLOT_LABELS: [string, string][] = [
  ["specialty", "Doctor"],
  ["day", "Day"],
  ["at", "Time"],
  ["name", "Name"],
  ["phone", "Phone"],
];

export default function DecisionPanel({ latest, history }: { latest: TurnResponse | null; history: TurnResponse[] }) {
  if (!latest) {
    return (
      <aside className="panel">
        <h2>What the brain decided</h2>
        <p className="muted">Decisions appear here after each turn.</p>
      </aside>
    );
  }
  const { trace } = latest;
  return (
    <aside className="panel">
      <h2>What the brain decided</h2>

      <section>
        <h3>State</h3>
        <p>
          <code>{trace.state_before}</code> → <code>{trace.state_after}</code>
          {latest.intent && (
            <>
              {" "}
              · intent <code>{latest.intent}</code>
            </>
          )}
        </p>
        <p>
          Rule fired: <code>{trace.rule || "—"}</code>
        </p>
      </section>

      <section>
        <h3>Heard</h3>
        <p>{trace.heard ? `“${trace.heard}”` : <span className="muted">(silence)</span>}</p>
        <p className="chips">
          {trace.intents.map((i) => (
            <span key={i} className="chip">
              {i}
            </span>
          ))}
          {Object.entries(trace.entities).map(([k, v]) => (
            <span key={k} className="chip entity">
              {k}: {v}
            </span>
          ))}
        </p>
      </section>

      <section>
        <h3>Slots</h3>
        <table>
          <tbody>
            {SLOT_LABELS.map(([key, label]) => (
              <tr key={key}>
                <td>{label}</td>
                <td className={latest.slots[key] ? "" : "muted"}>{latest.slots[key] ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {trace.notes.length > 0 && (
        <section>
          <h3>Notes</h3>
          <ul>
            {trace.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3>Turn log</h3>
        <ol className="log">
          {history.map((h, i) => (
            <li key={i}>
              <code>{h.trace.rule || "—"}</code>
              <span className="muted"> {h.trace.state_before} → {h.trace.state_after}</span>
            </li>
          ))}
        </ol>
      </section>
    </aside>
  );
}
