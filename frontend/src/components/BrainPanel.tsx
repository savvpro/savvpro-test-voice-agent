import type { Decision } from '../api'

export const label = (s: string) => {
  const t = s.replace(/_/g, ' ')
  return t.charAt(0).toUpperCase() + t.slice(1)
}

const pairs = (o: Record<string, string>) => Object.entries(o).map(([k, v]) => `${k}: ${v}`)

export default function BrainPanel({ decisions }: { decisions: Decision[] }) {
  const latest = decisions[0]
  return (
    <section aria-label="Decision panel" className="panel">
      <h2>Brain</h2>
      {!latest && <p className="muted">Decisions appear here after each turn.</p>}
      {latest && (
        <div className="slots">
          <h3>Filled slots</h3>
          {Object.keys(latest.slots).length === 0 ? (
            <p className="muted">None yet</p>
          ) : (
            <ul className="chips">
              {pairs(latest.slots).map((s) => (
                <li key={s} className="chip slot">{s}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      <ol className="decisions">
        {decisions.map((d, i) => (
          <li key={decisions.length - i} className="decision">
            <div className="action">{label(d.action)}</div>
            <dl>
              <dt>Intent</dt>
              <dd>{d.intent}</dd>
              <dt>State</dt>
              <dd>{d.state}</dd>
            </dl>
            {Object.keys(d.entities).length > 0 && (
              <ul className="chips" aria-label="Entities">
                {pairs(d.entities).map((e) => (
                  <li key={e} className="chip">{e}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}
