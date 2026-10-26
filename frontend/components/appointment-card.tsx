import { CalendarDays, CheckCheck, Clock3 } from "lucide-react";
import type { Business, Conversation } from "@/lib/types";

export function AppointmentCard({
  conversation,
  business,
}: {
  conversation: Conversation | null;
  business: Business | null;
}) {
  const saved = conversation?.appointment;
  const draft = conversation?.entities;
  const waiting = conversation?.state === "AWAITING_CONFIRMATION";
  const changing =
    saved && waiting && conversation?.proposed_action !== "create";
  const service =
    business?.services.find((item) => item.id === draft?.service)?.name ||
    draft?.service;
  return (
    <section
      className={`panel booking-card ${saved ? "success-card" : ""}`}
      aria-label={saved ? "Saved appointment" : "Appointment draft"}
    >
      <div className="booking-heading">
        <span className="booking-icon">
          {saved ? <CheckCheck size={20} /> : <CalendarDays size={20} />}
        </span>
        <div>
          <h3>
            {saved
              ? saved.status === "cancelled"
                ? "Appointment cancelled"
                : "Appointment confirmed"
              : "Your appointment"}
          </h3>
          <p>
            {saved
              ? "Saved appointment details"
              : waiting
                ? "Review details before confirming"
                : "Comes together as you talk"}
          </p>
        </div>
      </div>
      {saved ? (
        <div className="booking-detail">
          <strong>{saved.service_name}</strong>
          <span>
            {saved.starts_at.slice(0, 10)} · {saved.starts_at.slice(11, 16)}
          </span>
          <span>{saved.customer_name}</span>
          <code>{saved.reference}</code>
          <div className="booking-status confirmed">
            <span className="status-dot" />
            {saved.status}
          </div>
        </div>
      ) : draft?.service ? (
        <div className="booking-detail">
          <strong>{service}</strong>
          <span>
            {draft.date || "Date needed"} · {draft.time || "Time needed"}
          </span>
          <span>{draft.name || "Customer name needed"}</span>
          <div className="booking-status">
            <span className="status-dot" />
            {waiting ? "Needs explicit confirmation" : "Draft · not booked"}
          </div>
        </div>
      ) : (
        <div className="booking-empty">
          <CalendarDays size={26} strokeWidth={1} />
          <p>No appointment details yet</p>
          <span>Try “Book a haircut tomorrow at 3 PM”</span>
        </div>
      )}
      {changing && (
        <section className="proposed-change" aria-label="Proposed change">
          <strong>
            {conversation.proposed_action === "cancel"
              ? "Proposed cancellation"
              : "Proposed reschedule"}
          </strong>
          {conversation.proposed_action !== "cancel" && (
            <p>
              {service}
              <br />
              {draft?.date} · {draft?.time}
              <br />
              {draft?.name}
            </p>
          )}
          <p className="proposal-status">Needs explicit confirmation</p>
          <small>
            Your saved appointment stays unchanged until you confirm.
          </small>
        </section>
      )}
      {business && (
        <div className="timezone">
          <Clock3 size={14} />
          All times in {business.timezone}
        </div>
      )}
    </section>
  );
}
