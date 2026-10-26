"""
Dialogue Manager — the rule-based "brain" of the voice assistant.

This is the most important file in the repo. The brain MUST be our own code
(no LLM), so this is a hand-written finite state machine with slot filling.

Design overview
---------------
States flow like this for the happy path:

    GREETING -> ASK_DATE -> ASK_TIME -> ASK_PARTY_SIZE
            -> CHECK_AVAILABILITY -> ASK_NAME -> ASK_PHONE
            -> CONFIRM -> BOOKED -> GOODBYE

But callers are messy. The state machine also handles:
- multi-slot utterances ("tomorrow at 7 for 4 people" fills 3 slots at once)
- mid-flow changes ("actually change the time to 8pm")
- side questions ("wait, what time do you close?" — answered then returns)
- repeats, help requests, cancellations, fallbacks
- re-confirmation when a slot gets rejected

The state machine never asks the LLM anything. It runs entirely on
intent classification + slot extraction + a state table.

Public API
----------
- `DialogueManager.process(user_text, session) -> BrainResponse`

A `Session` is just a dict-like container with the current state, slots,
and the last prompt. The FastAPI app keeps one Session per caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .intents import classify, Intent
from . import slots as slot_extractor
from . import responses as R
from .restaurant import STORE


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------
class State:
    GREETING = "greeting"
    ASK_DATE = "ask_date"
    ASK_TIME = "ask_time"
    ASK_PARTY_SIZE = "ask_party_size"
    CHECK_AVAILABILITY = "check_availability"
    ASK_NAME = "ask_name"
    ASK_PHONE = "ask_phone"
    CONFIRM = "confirm"
    BOOKED = "booked"
    CANCELLED = "cancelled"
    GOODBYE = "goodbye"


# States where we are actively asking for a specific slot
_SLOT_ASKING_STATES = {
    State.ASK_DATE: "date",
    State.ASK_TIME: "time",
    State.ASK_PARTY_SIZE: "party_size",
    State.ASK_NAME: "name",
    State.ASK_PHONE: "phone",
}

# Meta intents that interrupt any state to answer a side question, then return.
_META_INTENTS = {"ask_hours", "ask_location", "ask_menu", "ask_parking", "repeat", "help"}


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
@dataclass
class Session:
    session_id: str
    state: str = State.GREETING
    slots: dict = field(default_factory=lambda: {
        "date": None, "time": None, "party_size": None, "name": None, "phone": None,
    })
    pending_booking_id: Optional[str] = None
    last_prompt: str = ""
    turns: int = 0
    history: list = field(default_factory=list)  # list of {role, text, intent, state}

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "state": self.state,
            "slots": dict(self.slots),
            "pending_booking_id": self.pending_booking_id,
            "last_prompt": self.last_prompt,
            "turns": self.turns,
            "history": list(self.history),
        }


@dataclass
class BrainResponse:
    text: str                   # what the assistant says
    state: str                  # new state
    slots: dict                 # new slot values
    intent: str                 # what we thought the user wanted
    decision: str               # human-readable label of what brain decided
    end_call: bool = False      # should the call end after this?
    booking_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Dialogue Manager
# ---------------------------------------------------------------------------
class DialogueManager:
    def __init__(self, store=STORE):
        self.store = store

    # ------------------------------------------------------------------
    def process(self, user_text: str, session: Session) -> BrainResponse:
        session.turns += 1
        intents = classify(user_text)
        top = intents[0]
        now = datetime.now()

        # Bookkeeping: record this turn in history.
        session.history.append({
            "role": "caller",
            "text": user_text,
            "intent": top.name,
            "confidence": round(top.confidence, 2),
            "state_before": session.state,
        })

        # 1) Hard interrupts that fire from any state.
        if top.name == "goodbye":
            return self._respond(R.goodbye(), State.GOODBYE, session, top.name, "end_call", end_call=True)
        if top.name == "cancel":
            return self._handle_cancel(session, top.name)
        if top.name == "silence":
            return self._respond(R.silence(), session.state, session, top.name, "silence_detected")
        if top.name == "help":
            return self._respond(
                "I can book a table, or tell you about our hours, location, menu, or parking. "
                "Just tell me what you'd like.",
                session.state, session, top.name, "help",
            )

        # 2) Meta side questions (hours/location/menu/parking/repeat).
        if top.name in _META_INTENTS:
            side_response = self._handle_meta(top.name, session)
            return self._respond(side_response, session.state, session, top.name, f"side_{top.name}")

        # 3) Terminal states.
        if session.state == State.GOODBYE:
            return self._respond(R.goodbye(), State.GOODBYE, session, top.name, "already_done", end_call=True)
        if session.state == State.BOOKED:
            # caller spoke after booking was confirmed
            if top.name == "confirm":
                return self._respond("You're all set. Anything else?", State.BOOKED, session, top.name, "already_booked")
            if top.name == "start_booking":
                # Start a brand new booking
                session.slots = {k: None for k in session.slots}
                session.pending_booking_id = None
                session.state = State.ASK_DATE
                return self._respond(R.ask_date(), State.ASK_DATE, session, top.name, "new_booking")
            return self._respond(R.goodbye(), State.GOODBYE, session, top.name, "wrap_up", end_call=True)

        # 4) GREETING state — either greet back, kick off a booking, or wait.
        if session.state == State.GREETING:
            if top.name == "greeting" and not any(_has_slot(intents, sn) for sn in ("date", "time", "party_size")):
                # bare "hi" — reply with greeting and prompt
                return self._respond(R.greet(), State.ASK_DATE, session, top.name, "greet_then_ask_date")
            # anything else (including "I want to book", or just "tomorrow") -> start
            return self._continue_booking(user_text, session, top, now)

        # 5) CONFIRM state
        if session.state == State.CONFIRM:
            if top.name == "confirm":
                return self._finalize_booking(session, top.name)
            if top.name == "deny":
                return self._respond(
                    "No problem. What would you like to change — the day, the time, or the party size?",
                    State.CONFIRM, session, top.name, "confirm_denied_offer_change",
                )
            if top.name == "change_value":
                # User said "actually change the time to 8pm"
                return self._try_change(user_text, session, top, now)
            # If user provides a fresh slot value mid-confirm, treat as a change
            new_slots = slot_extractor.extract_all(user_text, now)
            changed = {k: v for k, v in new_slots.items() if v is not None}
            if changed:
                return self._apply_changes(changed, session, top.name, now, source="confirm_change")

        # 6) In-flight slot-asking states — extract slots and advance.
        if session.state in _SLOT_ASKING_STATES:
            return self._continue_booking(user_text, session, top, now)

        # 7) CHECK_AVAILABILITY — basically a transient state, but if caller
        # speaks during it (shouldn't normally), treat as a change request.
        if session.state == State.CHECK_AVAILABILITY:
            return self._continue_booking(user_text, session, top, now)

        # 8) Fallback: we don't know what state we're in or what they want.
        return self._respond(R.did_not_understand(), session.state, session, top.name, "fallback")

    # ------------------------------------------------------------------
    # Continuation handler — used for any "in-progress" booking state.
    # ------------------------------------------------------------------
    def _continue_booking(self, user_text: str, session: Session, top: Intent, now: datetime) -> BrainResponse:
        # Confirm / deny mid-flow don't make sense unless we're in CONFIRM.
        if top.name == "confirm" and session.state not in (State.ASK_DATE, State.ASK_TIME, State.ASK_PARTY_SIZE, State.ASK_NAME, State.ASK_PHONE):
            return self._respond(R.empty_confirm(), State.ASK_DATE, session, top.name, "confirm_without_context")
        if top.name == "deny":
            return self._respond(R.empty_deny(), State.ASK_DATE, session, top.name, "deny_without_context")

        # Change requests: "actually change the time to 8pm"
        if top.name == "change_value":
            return self._try_change(user_text, session, top, now)

        # Extract all slots in one pass — supports multi-slot utterances.
        new_slots = slot_extractor.extract_all(user_text, now)
        filled = {k: v for k, v in new_slots.items() if v is not None}

        if not filled:
            # No slot extracted. Could be a fallback, or a yes/no out of context.
            if top.name == "fallback":
                return self._respond(R.did_not_understand(), session.state, session, top.name, "fallback_no_slot")
            # Some non-slot intent in a slot-asking state. Reprompt.
            return self._respond(
                self._reprompt_for_current_state(session),
                session.state, session, top.name, "reprompt",
            )

        # Merge filled slots into session
        for k, v in filled.items():
            session.slots[k] = v

        # Decide next state based on what's filled
        return self._advance(session, top.name, now, just_filled=list(filled.keys()))

    # ------------------------------------------------------------------
    # Advance state machine based on which slots are present.
    # ------------------------------------------------------------------
    def _advance(self, session: Session, intent_name: str, now: datetime, just_filled: list[str]) -> BrainResponse:
        s = session.slots
        # Required: date -> time -> party_size. Then availability. Then name -> phone -> confirm.
        if s["date"] is None:
            session.state = State.ASK_DATE
            return self._respond(R.ask_date(), State.ASK_DATE, session, intent_name, "need_date")
        if s["time"] is None:
            session.state = State.ASK_TIME
            return self._respond(R.ask_time(), State.ASK_TIME, session, intent_name, "need_time")
        if s["party_size"] is None:
            session.state = State.ASK_PARTY_SIZE
            return self._respond(R.ask_party_size(), State.ASK_PARTY_SIZE, session, intent_name, "need_party_size")

        # All three required slots are present. Check availability.
        if session.state != State.ASK_NAME and session.state != State.ASK_PHONE and session.state != State.CONFIRM:
            ok, reason = self.store.is_available(s["date"], s["time"], s["party_size"])
            if not ok:
                alts = self.store.suggest_alternatives(s["date"], s["party_size"], s["time"])
                # Reset the failed slot but keep the rest so the user can change just one.
                # We invalidate time first since that's the most common rejection cause.
                session.slots["time"] = None
                session.state = State.ASK_TIME
                return self._respond(
                    R.not_available(reason, alts),
                    State.ASK_TIME, session, intent_name, "availability_failed",
                )

        if s["name"] is None:
            session.state = State.ASK_NAME
            return self._respond(R.ask_name(), State.ASK_NAME, session, intent_name, "need_name")
        if s["phone"] is None:
            session.state = State.ASK_PHONE
            return self._respond(R.ask_phone(), State.ASK_PHONE, session, intent_name, "need_phone")

        # All slots filled — go to confirm.
        session.state = State.CONFIRM
        return self._respond(R.confirm(s), State.CONFIRM, session, intent_name, "confirm")

    # ------------------------------------------------------------------
    # Handle "actually change the time to 8pm" — figure out which slot to update.
    # ------------------------------------------------------------------
    def _try_change(self, user_text: str, session: Session, top: Intent, now: datetime) -> BrainResponse:
        new_slots = slot_extractor.extract_all(user_text, now)
        filled = {k: v for k, v in new_slots.items() if v is not None}

        if not filled:
            # User said "actually I want to change" but didn't say what to
            return self._respond(R.ask_change_what(), session.state, session, top.name, "change_what")

        return self._apply_changes(filled, session, top.name, now, source="change")

    def _apply_changes(self, changes: dict, session: Session, intent_name: str, now: datetime, source: str) -> BrainResponse:
        # Apply each change
        for k, v in changes.items():
            session.slots[k] = v

        # If date/time/party_size changed, we may need to re-check availability.
        # Reset any downstream slot whose validity depends on the changed slot.
        if any(k in changes for k in ("date", "time", "party_size")):
            # Re-validate
            s = session.slots
            if s["date"] and s["time"] and s["party_size"]:
                ok, reason = self.store.is_available(s["date"], s["time"], s["party_size"])
                if not ok:
                    alts = self.store.suggest_alternatives(s["date"], s["party_size"], s["time"])
                    session.slots["time"] = None
                    session.state = State.ASK_TIME
                    return self._respond(
                        R.not_available(reason, alts),
                        State.ASK_TIME, session, intent_name, f"{source}_revalidate_failed",
                    )
        # Re-advance from current state
        return self._advance(session, intent_name, now, just_filled=list(changes.keys()))

    # ------------------------------------------------------------------
    # Finalize booking — only callable from CONFIRM state after a "yes".
    # ------------------------------------------------------------------
    def _finalize_booking(self, session: Session, intent_name: str) -> BrainResponse:
        s = session.slots
        if not all([s["date"], s["time"], s["party_size"], s["name"], s["phone"]]):
            return self._respond(
                "Something's missing. Let me check what we still need.",
                State.ASK_DATE, session, intent_name, "finalize_incomplete",
            )
        try:
            booking = self.store.create_booking(s["date"], s["time"], s["party_size"], s["name"], s["phone"])
        except ValueError as e:
            # Race condition or invalid — fall back to asking for time
            session.slots["time"] = None
            session.state = State.ASK_TIME
            return self._respond(
                f"I couldn't finalize that. {e} Could you pick another time?",
                State.ASK_TIME, session, intent_name, "finalize_failed",
            )
        session.pending_booking_id = booking.booking_id
        session.state = State.BOOKED
        return self._respond(
            R.booked(booking.booking_id, s),
            State.BOOKED, session, intent_name, "booking_confirmed",
            booking_id=booking.booking_id,
        )

    # ------------------------------------------------------------------
    # Cancellation handler
    # ------------------------------------------------------------------
    def _handle_cancel(self, session: Session, intent_name: str) -> BrainResponse:
        if session.pending_booking_id:
            self.store.cancel_booking(session.pending_booking_id)
            session.pending_booking_id = None
        session.slots = {k: None for k in session.slots}
        session.state = State.CANCELLED
        return self._respond(R.cancelled(), State.CANCELLED, session, intent_name, "cancelled")

    # ------------------------------------------------------------------
    # Meta intents (side questions)
    # ------------------------------------------------------------------
    def _handle_meta(self, intent_name: str, session: Session) -> str:
        if intent_name == "ask_hours":
            return R.hours_info()
        if intent_name == "ask_location":
            return R.location_info()
        if intent_name == "ask_menu":
            return R.menu_info()
        if intent_name == "ask_parking":
            return R.parking_info()
        if intent_name == "repeat":
            return R.repeat_last(session.last_prompt or R.greet())
        return R.cannot_help()

    # ------------------------------------------------------------------
    # Reprompt helper
    # ------------------------------------------------------------------
    def _reprompt_for_current_state(self, session: Session) -> str:
        # Use if/elif (not a dict literal) so we only evaluate the branch we
        # actually return. R.confirm() would crash on None slots if the dict
        # were built eagerly for every state.
        st = session.state
        if st == State.ASK_DATE:
            return "What day would you like to book?"
        if st == State.ASK_TIME:
            return "What time would you like?"
        if st == State.ASK_PARTY_SIZE:
            return "How many people will be joining?"
        if st == State.ASK_NAME:
            return "What name should I put the reservation under?"
        if st == State.ASK_PHONE:
            return "What's a phone number we can reach you at?"
        if st == State.CONFIRM:
            # Defensive: only call R.confirm if we actually have the slots.
            s = session.slots
            if all(s.get(k) for k in ("date", "time", "party_size", "name", "phone")):
                return R.confirm(s)
            return "Could you confirm the booking?"
        if st == State.GREETING:
            return R.greet()
        return R.did_not_understand()

    # ------------------------------------------------------------------
    # Final response builder — also updates session.last_prompt and history.
    # ------------------------------------------------------------------
    def _respond(
        self,
        text: str,
        new_state: str,
        session: Session,
        intent: str,
        decision: str,
        end_call: bool = False,
        booking_id: Optional[str] = None,
    ) -> BrainResponse:
        session.state = new_state
        session.last_prompt = text
        session.history.append({
            "role": "assistant",
            "text": text,
            "state": new_state,
            "decision": decision,
        })
        return BrainResponse(
            text=text,
            state=new_state,
            slots=dict(session.slots),
            intent=intent,
            decision=decision,
            end_call=end_call,
            booking_id=booking_id or session.pending_booking_id,
        )


# ---------------------------------------------------------------------------
def _has_slot(intents: list[Intent], slot_name: str) -> bool:
    """Quick check whether any intent in the list corresponds to a slot.

    Used in GREETING to detect 'hi, I want to book tomorrow'.
    """
    slot_intents = {
        "date": "provide_date",
        "time": "provide_time",
        "party_size": "provide_party_size",
        "name": "provide_name",
        "phone": "provide_phone",
    }
    target = slot_intents.get(slot_name)
    return any(i.name == target for i in intents)


# Singleton dialogue manager
DM = DialogueManager()
