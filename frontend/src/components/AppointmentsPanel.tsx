import { useEffect, useState } from "react";
import { listAppointments } from "../api/client";
import type { Appointment } from "../api/types";

function when(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

/** Upcoming bookings straight from the database, newest first; reloads whenever `refreshKey` changes. */
export function AppointmentsPanel({ refreshKey, highlight }: { refreshKey: number; highlight?: string | null }) {
  const [items, setItems] = useState<Appointment[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listAppointments()
      .then((data) => !cancelled && (setItems(data), setError(null)))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <section className="panel appointments">
      <h2>
        Upcoming appointments <span className="muted small">newest bookings first</span>
      </h2>
      {error && <p className="error">{error}</p>}
      {!error && items.length === 0 && <p className="muted">No upcoming appointments.</p>}
      <ul>
        {items.slice(0, 12).map((a) => (
          <li key={a.booking_ref} className={a.booking_ref === highlight ? "new" : ""}>
            <code>
              {a.booking_ref}
              {a.booking_ref === highlight && <span className="badge">just booked</span>}
            </code>
            <span className="appt-main">
              {a.department} · {a.doctor}
            </span>
            <span className="muted">
              {when(a.start)} · {a.patient_name} · {a.phone}
            </span>
          </li>
        ))}
      </ul>
      {items.length > 12 && <p className="muted small">and {items.length - 12} more</p>}
    </section>
  );
}
