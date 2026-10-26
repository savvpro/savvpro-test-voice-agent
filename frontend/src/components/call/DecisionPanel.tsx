import type { Decision } from "@/lib/api";

type Props = { decision: Decision | null; index: number | null; total: number; onSelect: (i: number) => void };

export function DecisionPanel({ decision, index, total, onSelect }: Props) {
  return (
    <section className="card overflow-hidden" aria-label="What the brain decided">
      <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3.5">
        <h2 className="text-sm font-semibold text-ink-900">What the brain decided</h2>
        {total > 0 && index !== null && (
          <div className="flex items-center gap-1">
            <StepButton label="Previous turn" disabled={index === 0} onClick={() => onSelect(index - 1)} d="M15 6l-6 6 6 6" />
            <span className="w-16 text-center font-mono text-xs text-ink-500">
              turn {index + 1}/{total}
            </span>
            <StepButton label="Next turn" disabled={index >= total - 1} onClick={() => onSelect(index + 1)} d="M9 6l6 6-6 6" />
          </div>
        )}
      </div>

      {!decision ? (
        <p className="px-5 py-8 text-center text-sm text-ink-500">
          After you speak, each step of the decision appears here: what was heard, the intent, the details found, and
          why it picked its reply.
        </p>
      ) : (
        <div className="space-y-4 px-5 py-5 text-sm">
          <Row label="Heard">
            <span className="text-ink-900">“{decision.heard || "…"}”</span>
          </Row>
          <Row label="Cleaned">
            <code className="font-mono text-xs text-ink-600">{decision.normalized || "(nothing)"}</code>
          </Row>
          <Row label="Intent">
            <div className="flex items-center gap-3">
              <span className="chip font-mono">{decision.intent ?? "none"}</span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-100" aria-hidden>
                <div className="h-full rounded-full bg-ink-800 transition-all" style={{ width: `${Math.round(decision.confidence * 100)}%` }} />
              </div>
              <span className="font-mono text-xs text-ink-500">{decision.confidence.toFixed(2)}</span>
            </div>
          </Row>
          <Row label="Details">
            {Object.keys(decision.extracted).length ? (
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(decision.extracted).map(([k, v]) => (
                  <span key={k} className="chip">
                    <span className="text-ink-400">{k}</span> {formatValue(v)}
                  </span>
                ))}
              </div>
            ) : (
              <span className="text-ink-400">none found</span>
            )}
          </Row>
          <Row label="Why">
            {decision.reasons.length ? (
              <ol className="space-y-1.5">
                {decision.reasons.map((r, i) => (
                  <li key={i} className="flex gap-2 text-ink-700">
                    <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-ink-500" />
                    {r}
                  </li>
                ))}
              </ol>
            ) : (
              <span className="text-ink-400">Next step in the flow</span>
            )}
          </Row>
          <Row label="Action">
            <span className="inline-flex items-center rounded-md bg-ink-900 px-2 py-0.5 font-mono text-xs text-white">{decision.action}</span>
          </Row>
        </div>
      )}
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[72px_1fr] items-start gap-3">
      <span className="pt-0.5 text-xs font-medium uppercase tracking-wider text-ink-400">{label}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function StepButton({ label, disabled, onClick, d }: { label: string; disabled: boolean; onClick: () => void; d: string }) {
  return (
    <button type="button" aria-label={label} disabled={disabled} onClick={onClick} className="rounded-md p-1 text-ink-600 hover:bg-ink-100 disabled:opacity-30">
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <path d={d} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}

function formatValue(v: unknown): string {
  if (v && typeof v === "object" && "value" in v) {
    const t = v as { value: string; explicit_meridiem: boolean };
    return t.explicit_meridiem ? t.value.slice(0, 5) : `${t.value.slice(0, 5)} (no AM/PM)`;
  }
  return String(v);
}
