import type { Booking } from "@/lib/api";

export function SchedulePanel({ bookings, onReset }: { bookings: Booking[]; onReset: () => void }) {
  return (
    <section className="card" aria-label="Appointment book">
      <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3.5">
        <h2 className="text-sm font-semibold text-ink-900">Appointment book</h2>
        <button type="button" onClick={onReset} className="text-xs font-medium text-ink-500 underline-offset-2 hover:text-ink-900 hover:underline">
          Reset demo data
        </button>
      </div>
      {bookings.length === 0 ? (
        <p className="px-5 py-6 text-center text-sm text-ink-500">No bookings yet.</p>
      ) : (
        <ul className="divide-y divide-ink-100">
          {bookings.map((b) => (
            <li key={b.id} className="flex items-center justify-between gap-3 px-5 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink-900">
                  {b.name} <span className="font-normal text-ink-500">· {b.service}</span>
                </p>
                <p className="text-xs text-ink-500">{b.when}</p>
              </div>
              <span className="shrink-0 font-mono text-xs text-ink-400">{b.id}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="border-t border-ink-100 px-5 py-2.5 text-[11px] text-ink-400">
        Fake data. Try moving or cancelling Jordan Lee&apos;s visit: just say the name.
      </p>
    </section>
  );
}
