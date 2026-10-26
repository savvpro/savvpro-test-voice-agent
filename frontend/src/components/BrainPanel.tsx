import type { TurnResponse } from "../api/types";

const FRAME_FIELDS = [
  "task",
  "department",
  "doctor",
  "date",
  "time",
  "time_of_day",
  "patient_name",
  "phone",
  "booking_ref",
  "chosen_slot",
] as const;

function show(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") {
    const v = value as Record<string, unknown>;
    if ("label" in v) return String(v.label); // time of day
    if ("start" in v && "doctor" in v) return `${String(v.start).replace("T", " ").slice(0, 16)} · ${v.doctor}`;
    return JSON.stringify(value);
  }
  return String(value);
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const level = value >= 0.8 ? "high" : value >= 0.6 ? "mid" : "low";
  return (
    <div className="confidence" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="confidence">
      <div className={`fill ${level}`} style={{ width: `${pct}%` }} />
      <span>{pct}%</span>
    </div>
  );
}

/** What the brain made of the last turn: NLU, dialogue state and timings. */
export function BrainPanel({ turn }: { turn: TurnResponse | null }) {
  if (!turn) {
    return (
      <section className="panel brain">
        <h2>Brain</h2>
        <p className="muted">Each turn's intent, entities and dialogue state show up here.</p>
      </section>
    );
  }
  const { nlu, decision, timings_ms: t } = turn;
  const entities = nlu ? Object.entries(nlu.entities).filter(([, v]) => v !== null) : [];

  return (
    <section className="panel brain">
      <h2>Brain</h2>
      {nlu ? (
        <>
          <div className="row">
            <span className="label">Intent</span>
            <strong className="intent">{nlu.intent}</strong>
            <span className={`source source-${nlu.source}`} title="which part of the NLU decided">
              {nlu.source}
            </span>
          </div>
          <ConfidenceBar value={nlu.confidence} />
          <div className="row top">
            <span className="label">Top 3 (classifier)</span>
            <ol className="alternatives">
              {nlu.alternatives.slice(0, 3).map((a) => (
                <li key={a.intent}>
                  {a.intent} <span className="muted">{a.confidence.toFixed(2)}</span>
                </li>
              ))}
            </ol>
          </div>
          <div className="row top">
            <span className="label">Entities</span>
            {entities.length ? (
              <dl className="kv">
                {entities.map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{show(v)}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <span className="muted">none</span>
            )}
          </div>
        </>
      ) : (
        <p className="muted">Greeting turn (no caller input yet).</p>
      )}
      <div className="row">
        <span className="label">State</span>
        <code className="state">{decision.state}</code>
        {decision.action && <span className="action">{decision.action}</span>}
      </div>
      <div className="row top">
        <span className="label">Frame</span>
        <dl className="kv">
          {FRAME_FIELDS.map((k) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{show(decision.frame[k])}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="row timings">
        <span className="label">Timings</span>
        <span>STT {t.stt} ms</span>
        <span>NLU {t.nlu} ms</span>
        <span>DM {t.dm} ms</span>
        <span>TTS {t.tts} ms</span>
      </div>
      {turn.transcript_confidence !== null && (
        <p className="muted small">Speech recognition confidence: {Math.round(turn.transcript_confidence * 100)}%</p>
      )}
    </section>
  );
}
