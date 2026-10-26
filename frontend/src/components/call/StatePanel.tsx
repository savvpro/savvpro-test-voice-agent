import type { CallState } from "@/lib/api";

const FIELDS: [keyof CallState, string][] = [
  ["task", "Job"],
  ["service", "Visit"],
  ["day", "Day"],
  ["at", "Time"],
  ["name", "Name"],
  ["phone", "Phone (optional)"],
];

export function StatePanel({ state }: { state: CallState | null }) {
  return (
    <section className="card" aria-label="What it knows so far">
      <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3.5">
        <h2 className="text-sm font-semibold text-ink-900">What it knows so far</h2>
        {state?.awaiting && (
          <span className="chip">
            waiting for <span className="font-mono">{state.awaiting}</span>
          </span>
        )}
      </div>
      <dl className="grid grid-cols-2 gap-px bg-ink-100 sm:grid-cols-3">
        {FIELDS.map(([key, label]) => {
          const raw = state?.[key];
          // Phone numbers stay private on screen: only the last four digits show.
          const value =
            key === "phone" ? (typeof raw === "string" ? `ends in ${raw.slice(-4)}` : state?.phone_skipped ? "skipped" : null) : raw;
          return (
            <div key={key} className="bg-white px-5 py-3">
              <dt className="text-[11px] font-medium uppercase tracking-wider text-ink-400">{label}</dt>
              <dd className={`mt-0.5 truncate text-sm ${value ? "font-medium text-ink-900" : "text-ink-300"}`}>{value ? String(value) : "—"}</dd>
            </div>
          );
        })}
      </dl>
      {state && (state.offers.length > 0 || state.result || state.misses > 0) && (
        <div className="space-y-1 border-t border-ink-100 px-5 py-3 text-xs text-ink-600">
          {state.offers.length > 0 && <p>Offered: {state.offers.join(" · ")}</p>}
          {state.misses > 0 && <p>Not understood: {state.misses} of 3 before transfer</p>}
          {state.result && <p className="font-medium text-ink-900">Result: {state.result}</p>}
        </div>
      )}
    </section>
  );
}
