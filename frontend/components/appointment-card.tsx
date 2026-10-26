import { CalendarDays, Check, Clock3, Mic } from "lucide-react";
import type { Business, Conversation } from "@/lib/types";

export function AppointmentCard({
  conversation,
  business,
  disabled,
  onStartBooking,
  onContinue,
  onManage,
}: {
  conversation: Conversation | null;
  business: Business | null;
  disabled: boolean;
  onStartBooking: () => void;
  onContinue: () => void;
  onManage: (action: "reschedule" | "cancel", reference: string) => void;
}) {
  const saved = conversation?.appointment;
  const draft = conversation?.entities;
  const waiting = conversation?.state === "AWAITING_CONFIRMATION";
  const changing =
    saved && waiting && conversation?.proposed_action !== "create";
  const hasDraft = Boolean(
    draft?.service || draft?.date || draft?.time || draft?.name,
  );
  const selectedService = business?.services.find(
    (item) => item.id === (saved?.service || draft?.service),
  );
  const draftService = business?.services.find(
    (item) => item.id === draft?.service,
  );
  const timezone = saved?.timezone || business?.timezone;
  const duration = saved
    ? Math.round(
        (Date.parse(saved.ends_at) - Date.parse(saved.starts_at)) / 60000,
      )
    : selectedService?.minutes;
  const price =
    selectedService && business
      ? `${business.currency} ${selectedService.price.toLocaleString("en-PK")}`
      : "—";
  const savedDate = saved
    ? new Intl.DateTimeFormat("en-GB", {
        weekday: "long",
        day: "2-digit",
        month: "short",
        year: "numeric",
        timeZone: saved.timezone,
      }).format(new Date(saved.starts_at))
    : null;

  return (
    <section
      className={`panel booking-card ${saved ? "success-card" : !hasDraft ? "empty-booking-card" : "draft-booking-card"}`}
      aria-label={saved ? "Saved appointment" : "Appointment draft"}
    >
      {saved ? (
        <div className="booking-detail">
          <div className="booking-summary-top">
            <span
              className={`booking-status ${saved.status === "confirmed" ? "confirmed" : "cancelled"}`}
            >
              {saved.status === "confirmed" ? (
                <Check size={12} />
              ) : (
                <span className="status-dot" />
              )}
              {saved.status}
            </span>
            <code>{saved.reference}</code>
          </div>
          <h2>{saved.service_name}</h2>
          <time dateTime={saved.starts_at}>
            {savedDate} · {saved.starts_at.slice(11, 16)}
          </time>
          <dl className="appointment-facts">
            <div>
              <dt>Name</dt>
              <dd>{saved.customer_name}</dd>
            </div>
            <div>
              <dt>Duration</dt>
              <dd>{duration} min</dd>
            </div>
            <div>
              <dt>Price</dt>
              <dd>{price}</dd>
            </div>
          </dl>
          {saved.status === "confirmed" && (
            <div className="appointment-actions">
              <button
                className="button secondary"
                disabled={disabled}
                onClick={() => onManage("reschedule", saved.reference)}
              >
                Reschedule
              </button>
              <button
                className="button secondary"
                disabled={disabled}
                onClick={() => onManage("cancel", saved.reference)}
              >
                Cancel booking
              </button>
            </div>
          )}
        </div>
      ) : hasDraft ? (
        <div className="booking-detail">
          <div className="booking-summary-top">
            <span className="booking-status">
              <span className="status-dot" />
              {waiting ? "Needs explicit confirmation" : "Draft · not booked"}
            </span>
          </div>
          <h2>{draftService?.name || "Appointment draft"}</h2>
          <p className="booking-draft-date">
            {draft?.date || "Date needed"} · {draft?.time || "Time needed"}
          </p>
          <dl className="appointment-facts">
            <div>
              <dt>Name</dt>
              <dd>{draft?.name || "Customer name needed"}</dd>
            </div>
            <div>
              <dt>Duration</dt>
              <dd>{duration ? `${duration} min` : "Service needed"}</dd>
            </div>
            <div>
              <dt>Price</dt>
              <dd>{price}</dd>
            </div>
          </dl>
          <button className="button secondary" onClick={onContinue}>
            Continue in conversation
          </button>
        </div>
      ) : (
        <div className="booking-empty">
          <span className="booking-icon">
            <CalendarDays size={23} strokeWidth={1.5} />
          </span>
          <h2>No appointment yet</h2>
          <p>
            Start a conversation and your booking will appear here as it takes
            shape.
          </p>
          <button
            className="button secondary"
            disabled={disabled}
            onClick={onStartBooking}
          >
            <Mic size={13} /> Book a haircut tomorrow at 3 PM
          </button>
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
              {draftService?.name || draft?.service}
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
          <button className="button secondary" onClick={onContinue}>
            Review in conversation
          </button>
        </section>
      )}
      {timezone && (
        <div className="timezone">
          <Clock3 size={12} />
          All times in {timezone}
        </div>
      )}
    </section>
  );
}
