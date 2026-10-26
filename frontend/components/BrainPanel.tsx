import type { Slots } from "@/lib/api";
import { slotRows, stateLabel } from "@/lib/labels";

type Props = {
  state: string;
  slots: Slots;
  intents: string[];
  actions: string[];
  trace: string[];
};

export default function BrainPanel({ state, slots, intents, actions, trace }: Props) {
  return (
    <div className="stack" aria-label="What the brain is doing">
      <section className="card">
        <h2>State</h2>
        <span className="state">{stateLabel(state)}</span>
        <ul className="slots">
          {slotRows(slots).map((row) => (
            <li key={row.label}>
              <span className="label">{row.label}</span>
              {row.value ? <strong>{row.value}</strong> : <span className="missing">not yet</span>}
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Last sentence understood as</h2>
        {intents.length ? (
          <div className="chips">
            {intents.map((intent) => (
              <span className="chip" key={intent}>{intent}</span>
            ))}
          </div>
        ) : (
          <span className="missing">no intent yet</span>
        )}
        <h2 style={{ marginTop: 14 }}>Replies used</h2>
        {actions.length ? (
          <div className="chips">
            {actions.map((action, index) => (
              <span className="chip" key={`${action}-${index}`}>{action}</span>
            ))}
          </div>
        ) : (
          <span className="missing">none yet</span>
        )}
      </section>

      <section className="card">
        <h2>Why</h2>
        {trace.length ? (
          <ol className="trace">
            {trace.map((line, index) => (
              <li key={index}>{line}</li>
            ))}
          </ol>
        ) : (
          <span className="missing">Start a call to see the rules fire.</span>
        )}
      </section>
    </div>
  );
}
