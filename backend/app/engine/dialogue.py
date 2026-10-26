"""State-machine dialogue brain for Harbor Lights Bistro bookings.

No LLM. Decisions come from explicit states + deterministic parsing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.engine import availability
from app.engine.availability import SERVICE_TIMES
from app.engine.parser import parse_utterance
from app.models import (
    Booking,
    ConfirmationTicket,
    DecisionTrace,
    DialogueState,
    Slots,
    TurnResponse,
)
from app.notifications import log_confirmation


RESTAURANT = "Harbor Lights Bistro"

# Friendly time display
def _fmt_time(t: str) -> str:
    h, m = map(int, t.split(":"))
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def _fmt_date(d: str) -> str:
    try:
        dt = date.fromisoformat(d)
        return dt.strftime("%A, %B %-d") if hasattr(dt, "strftime") else d
    except ValueError:
        return d


def _fmt_date_safe(d: str) -> str:
    try:
        dt = date.fromisoformat(d)
        # %-d is platform-specific; use plain day number
        return dt.strftime("%A, %B ") + str(dt.day)
    except ValueError:
        return d


@dataclass
class Session:
    session_id: str
    state: DialogueState = DialogueState.GREETING
    slots: Slots = field(default_factory=Slots)
    booking: Optional[Booking] = None
    pending_alternatives: list[str] = field(default_factory=list)
    turns: int = 0


class DialogueEngine:
    """Per-process session map + turn handler."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id=session_id)
        return self._sessions[session_id]

    def reset(self, session_id: str) -> TurnResponse:
        self._sessions[session_id] = Session(session_id=session_id)
        sess = self._sessions[session_id]
        reply = (
            f"Hi — thanks for calling {RESTAURANT}. "
            "I can help you book a table. What day works for you?"
        )
        sess.state = DialogueState.ASK_DATE
        return TurnResponse(
            reply=reply,
            state=sess.state.value,
            slots=sess.slots.model_copy(),
            decision=DecisionTrace(
                state_before=DialogueState.GREETING.value,
                state_after=sess.state.value,
                intent="reset",
                action="start_fresh",
                notes=["session reset"],
            ),
            booking=None,
        )

    def handle_turn(self, session_id: str, text: str) -> TurnResponse:
        sess = self.get_or_create(session_id)
        state_before = sess.state
        sess.turns += 1

        # Already finished
        if sess.state in (DialogueState.GOODBYE, DialogueState.CANCELLED):
            return self._respond(
                sess,
                state_before,
                intent="noop",
                action="session_ended",
                reply=(
                    "This booking call has ended. "
                    "Hit Reset if you'd like to start another one."
                ),
                notes=["terminal state"],
            )

        if sess.state == DialogueState.BOOKED:
            parsed = parse_utterance(text)
            if parsed.intent == "cancel":
                return self._goodbye(sess, state_before, parsed.intent)
            return self._respond(
                sess,
                state_before,
                intent=parsed.intent,
                action="already_booked",
                reply=(
                    f"You're all set — confirmation {sess.booking.id if sess.booking else 'ready'}. "
                    "Say goodbye when you're done, or hit Reset for a new booking."
                ),
                notes=parsed.notes,
            )

        parsed = parse_utterance(text)

        # Global cancel
        if parsed.intent == "cancel":
            sess.state = DialogueState.CANCELLED
            return self._respond(
                sess,
                state_before,
                intent="cancel",
                action="cancel_booking",
                reply="No problem — I've cancelled this booking. Have a good one.",
                notes=parsed.notes,
            )

        # Out of scope
        if parsed.intent == "out_of_scope":
            return self._respond(
                sess,
                state_before,
                intent="out_of_scope",
                action="redirect",
                reply=(
                    f"I only handle table bookings for {RESTAURANT}. "
                    + self._prompt_for(sess.state, sess.slots)
                ),
                notes=parsed.notes,
            )

        # Apply any slots the caller volunteered (supports mid-flow changes)
        slots_updated: dict = {}
        if parsed.date:
            sess.slots.date = parsed.date
            slots_updated["date"] = parsed.date
            sess.pending_alternatives = []
        if parsed.time:
            # Validate service hours
            if parsed.time not in SERVICE_TIMES:
                return self._respond(
                    sess,
                    state_before,
                    intent=parsed.intent,
                    action="reject_time",
                    reply=(
                        f"We're open for dinner from 5:00 PM to 9:00 PM, "
                        f"every half hour. {_fmt_time(parsed.time)} isn't a slot we offer. "
                        "What time would you like?"
                    ),
                    slots_updated=slots_updated,
                    notes=parsed.notes + ["time outside service hours"],
                )
            sess.slots.time = parsed.time
            slots_updated["time"] = parsed.time
            sess.pending_alternatives = []
        if parsed.party_size:
            sess.slots.party_size = parsed.party_size
            slots_updated["party_size"] = parsed.party_size
            sess.pending_alternatives = []
        if parsed.guest_name:
            sess.slots.guest_name = parsed.guest_name
            slots_updated["guest_name"] = parsed.guest_name

        # Explicit change intents with no new value → re-ask that slot
        if parsed.intent == "change_date" and "date" not in slots_updated:
            sess.state = DialogueState.ASK_DATE
            return self._respond(
                sess,
                state_before,
                intent=parsed.intent,
                action="reask_date",
                reply="Sure — what day would you like instead?",
                slots_updated=slots_updated,
                notes=parsed.notes,
            )
        if parsed.intent == "change_time" and "time" not in slots_updated:
            sess.state = DialogueState.ASK_TIME
            return self._respond(
                sess,
                state_before,
                intent=parsed.intent,
                action="reask_time",
                reply="Okay — what time works better?",
                slots_updated=slots_updated,
                notes=parsed.notes,
            )
        if parsed.intent == "change_party" and "party_size" not in slots_updated:
            sess.state = DialogueState.ASK_PARTY
            return self._respond(
                sess,
                state_before,
                intent=parsed.intent,
                action="reask_party",
                reply="Got it — how many people will be joining?",
                slots_updated=slots_updated,
                notes=parsed.notes,
            )

        # Greeting / start
        if sess.state == DialogueState.GREETING:
            sess.state = DialogueState.ASK_DATE
            if not slots_updated:
                return self._respond(
                    sess,
                    state_before,
                    intent=parsed.intent,
                    action="greet",
                    reply=(
                        f"Hi — thanks for calling {RESTAURANT}. "
                        "I can book you a table. What day works for you?"
                    ),
                    notes=parsed.notes,
                )
            # Fall through if they already gave info in the first utterance

        # Advance through missing slots
        return self._advance(sess, state_before, parsed.intent, slots_updated, parsed.notes)

    def _advance(
        self,
        sess: Session,
        state_before: DialogueState,
        intent: str,
        slots_updated: dict,
        notes: list[str],
    ) -> TurnResponse:
        # Fill missing pieces in order: date → time → party → confirm
        if not sess.slots.date:
            sess.state = DialogueState.ASK_DATE
            if intent == "unclear" and not slots_updated:
                return self._respond(
                    sess,
                    state_before,
                    intent=intent,
                    action="clarify_date",
                    reply=(
                        "I didn't catch a date. You can say something like "
                        "'tomorrow', 'Friday', or 'October 30'."
                    ),
                    slots_updated=slots_updated,
                    notes=notes,
                )
            return self._respond(
                sess,
                state_before,
                intent=intent,
                action="ask_date",
                reply="What day would you like to come in?",
                slots_updated=slots_updated,
                notes=notes,
            )

        if not sess.slots.time:
            sess.state = DialogueState.ASK_TIME
            if intent == "unclear" and not slots_updated:
                return self._respond(
                    sess,
                    state_before,
                    intent=intent,
                    action="clarify_time",
                    reply=(
                        "I need a time — we're open 5:00 PM to 9:00 PM. "
                        "For example, '7 PM' or '7:30'."
                    ),
                    slots_updated=slots_updated,
                    notes=notes,
                )
            return self._respond(
                sess,
                state_before,
                intent=intent,
                action="ask_time",
                reply=(
                    f"Okay, {_fmt_date_safe(sess.slots.date)}. "
                    "What time? We seat every half hour from 5 to 9 PM."
                ),
                slots_updated=slots_updated,
                notes=notes,
            )

        if not sess.slots.party_size:
            sess.state = DialogueState.ASK_PARTY
            if intent == "unclear" and not slots_updated:
                return self._respond(
                    sess,
                    state_before,
                    intent=intent,
                    action="clarify_party",
                    reply="How many people? Just a number is fine — say '4' or 'party of 4'.",
                    slots_updated=slots_updated,
                    notes=notes,
                )
            return self._respond(
                sess,
                state_before,
                intent=intent,
                action="ask_party",
                reply=f"And how many people for {_fmt_time(sess.slots.time)}?",
                slots_updated=slots_updated,
                notes=notes,
            )

        # All slots filled — availability / confirm / book
        return self._check_and_confirm(sess, state_before, intent, slots_updated, notes)

    def _check_and_confirm(
        self,
        sess: Session,
        state_before: DialogueState,
        intent: str,
        slots_updated: dict,
        notes: list[str],
    ) -> TurnResponse:
        assert sess.slots.date and sess.slots.time and sess.slots.party_size

        # If caller just denied at confirm, re-ask what to change
        if sess.state == DialogueState.CONFIRM and intent == "deny":
            sess.state = DialogueState.ASK_DATE
            # Clear so they re-specify; keep party as a convenience? Clear all for simplicity.
            return self._respond(
                sess,
                state_before,
                intent=intent,
                action="revise",
                reply=(
                    "No worries. Tell me the new day, time, or party size — "
                    "or say them all at once."
                ),
                slots_updated=slots_updated,
                notes=notes,
            )

        # Selecting an alternative time by saying it (already in slots_updated)
        # or confirming a pending alternative list
        available = availability.store.is_available(
            sess.slots.date, sess.slots.time, sess.slots.party_size
        )

        if not available:
            alts = availability.store.alternatives(
                sess.slots.date, sess.slots.time, sess.slots.party_size
            )
            sess.pending_alternatives = alts
            sess.state = DialogueState.ASK_TIME
            # Keep date + party; clear the unavailable time so next provide_info sets a new one
            bad_time = sess.slots.time
            sess.slots.time = None
            if alts:
                alt_str = ", ".join(_fmt_time(a) for a in alts)
                reply = (
                    f"Sorry — {_fmt_time(bad_time)} on {_fmt_date_safe(sess.slots.date)} "
                    f"is full for a party of {sess.slots.party_size}. "
                    f"I still have {alt_str}. Which works?"
                )
            else:
                reply = (
                    f"Sorry — {_fmt_date_safe(sess.slots.date)} is fully booked "
                    f"for a party of {sess.slots.party_size}. "
                    "Want to try a different day?"
                )
                sess.state = DialogueState.ASK_DATE
                sess.slots.date = None
            return self._respond(
                sess,
                state_before,
                intent=intent,
                action="offer_alternatives",
                reply=reply,
                slots_updated={**slots_updated, "time": None},
                notes=notes + ["slot unavailable"],
                alternatives=alts,
            )

        # Available — move to confirm, or book if they confirmed
        summary = (
            f"{sess.slots.party_size} on {_fmt_date_safe(sess.slots.date)} "
            f"at {_fmt_time(sess.slots.time)}"
        )

        if sess.state == DialogueState.CONFIRM and intent == "confirm":
            return self._do_book(sess, state_before, intent, slots_updated, notes)

        # If they just filled the last slot in one breath and said "book it"
        if intent == "confirm" and state_before != DialogueState.CONFIRM:
            # Jump straight to booking when they affirm with full slots
            return self._do_book(sess, state_before, intent, slots_updated, notes)

        sess.state = DialogueState.CONFIRM
        name_bit = (
            f" under {sess.slots.guest_name}" if sess.slots.guest_name else ""
        )
        return self._respond(
            sess,
            state_before,
            intent=intent,
            action="ask_confirm",
            reply=(
                f"I can do a table for {summary}{name_bit}. "
                "Should I book that?"
            ),
            slots_updated=slots_updated,
            notes=notes,
        )

    def _do_book(
        self,
        sess: Session,
        state_before: DialogueState,
        intent: str,
        slots_updated: dict,
        notes: list[str],
    ) -> TurnResponse:
        rec = availability.store.book(
            sess.slots.date,  # type: ignore[arg-type]
            sess.slots.time,  # type: ignore[arg-type]
            sess.slots.party_size,  # type: ignore[arg-type]
            sess.slots.guest_name,
        )
        if not rec:
            # Race / edge case
            sess.state = DialogueState.ASK_TIME
            sess.slots.time = None
            return self._respond(
                sess,
                state_before,
                intent=intent,
                action="book_failed",
                reply="That slot just filled up. Want a different time?",
                slots_updated=slots_updated,
                notes=notes + ["book failed"],
            )

        booking = Booking(
            id=rec.id,
            date=rec.date,
            time=rec.time,
            party_size=rec.party_size,
            guest_name=rec.guest_name,
            table_label=rec.table_label,
            status=getattr(rec, "status", "active"),
            created_at=getattr(rec, "created_at", None),
        )
        # Fake email/SMS — log only, never sent (free local demo)
        try:
            log_confirmation(
                booking_id=rec.id,
                date=rec.date,
                time=rec.time,
                party_size=rec.party_size,
                guest_name=rec.guest_name,
                restaurant=RESTAURANT,
            )
            notif_ok = True
        except OSError:
            notif_ok = False
        confirmation = ConfirmationTicket(
            code=rec.id,
            restaurant=RESTAURANT,
            datetime_display=f"{_fmt_date_safe(rec.date)} at {_fmt_time(rec.time)}",
            date=rec.date,
            time=rec.time,
            party_size=rec.party_size,
            table_label=rec.table_label,
            guest_name=rec.guest_name,
            notification_logged=notif_ok,
        )
        sess.booking = booking
        sess.state = DialogueState.BOOKED
        name_bit = f" for {rec.guest_name}" if rec.guest_name else ""
        reply = (
            f"Booked{name_bit}. Confirmation {rec.id}: "
            f"table {rec.table_label}, party of {rec.party_size}, "
            f"{_fmt_date_safe(rec.date)} at {_fmt_time(rec.time)}. "
            f"We'll see you at {RESTAURANT}. Anything else, or shall we wrap up?"
        )
        return self._respond(
            sess,
            state_before,
            intent=intent,
            action="booked",
            reply=reply,
            slots_updated=slots_updated,
            notes=notes + (["notification_logged"] if notif_ok else []),
            booking=booking,
            confirmation=confirmation,
        )

    def _goodbye(
        self, sess: Session, state_before: DialogueState, intent: str
    ) -> TurnResponse:
        sess.state = DialogueState.GOODBYE
        return self._respond(
            sess,
            state_before,
            intent=intent,
            action="goodbye",
            reply="Thanks for calling Harbor Lights Bistro. Enjoy your meal — goodbye!",
            notes=[],
        )

    def _prompt_for(self, state: DialogueState, slots: Optional[Slots] = None) -> str:
        if state == DialogueState.ASK_DATE or (slots and not slots.date):
            return "What day would you like?"
        if state == DialogueState.ASK_TIME or (slots and not slots.time):
            return "What time works?"
        if state == DialogueState.ASK_PARTY or (slots and not slots.party_size):
            return "How many people?"
        if state == DialogueState.CONFIRM:
            return "Should I go ahead and book it?"
        return "How can I help with a reservation?"

    def _respond(
        self,
        sess: Session,
        state_before: DialogueState,
        *,
        intent: str,
        action: str,
        reply: str,
        slots_updated: Optional[dict] = None,
        notes: Optional[list[str]] = None,
        booking: Optional[Booking] = None,
        confirmation: Optional[ConfirmationTicket] = None,
        alternatives: Optional[list[str]] = None,
    ) -> TurnResponse:
        return TurnResponse(
            reply=reply,
            state=sess.state.value,
            slots=sess.slots.model_copy(),
            decision=DecisionTrace(
                state_before=state_before.value,
                state_after=sess.state.value,
                intent=intent,
                slots_updated=slots_updated or {},
                action=action,
                notes=notes or [],
            ),
            booking=booking or sess.booking,
            confirmation=confirmation,
            alternatives=alternatives or [],
        )

