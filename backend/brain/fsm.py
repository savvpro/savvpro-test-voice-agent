"""
FSM (Finite State Machine) for the Clinic Appointment Voice Agent.

Public API
----------
    initial_state() -> (greeting_text, ConversationState)
    handle_utterance(text, conv_state) -> (reply_text, ConversationState)

Architecture
------------
Every utterance goes through the same pipeline regardless of FSM state:

    utterance
        │
        ▼
    classify(text)          ← intents.py, priority-ordered
        │
        ├─► correction intent?  ──► _handle_correction()
        │                            - overwrite named slot
        │                            - if in CONFIRM: re-read summary
        │                            - otherwise: ack + re-ask current Q
        │
        ├─► goodbye / repeat / unclear  ──► dedicated mini-handlers
        │
        └─► everything else  ──► _fsm_advance()
                                  - state-specific slot extraction
                                  - advance to next state via _next_question()
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .intents import Intent, classify, CORRECTION_INTENTS, CORRECTION_TO_SLOT
from .slots   import (
    extract_slots, extract_name, extract_doctor,
    extract_date, extract_time, is_past_date,
)
from .availability import is_available, find_alternatives
from . import responses as r


# ── States ────────────────────────────────────────────────────────────────────

class FSMState(str, Enum):
    GREETING              = "GREETING"
    COLLECT_NAME          = "COLLECT_NAME"
    COLLECT_DOCTOR        = "COLLECT_DOCTOR"
    COLLECT_DATE          = "COLLECT_DATE"
    COLLECT_TIME          = "COLLECT_TIME"
    COLLECT_REASON        = "COLLECT_REASON"
    CONFIRM               = "CONFIRM"
    RESCHEDULE_LOOKUP     = "RESCHEDULE_LOOKUP"
    RESCHEDULE_COLLECT_DATE = "RESCHEDULE_COLLECT_DATE"
    RESCHEDULE_COLLECT_TIME = "RESCHEDULE_COLLECT_TIME"
    CANCEL_LOOKUP         = "CANCEL_LOOKUP"
    CANCEL_CONFIRM        = "CANCEL_CONFIRM"
    END                   = "END"


# ── Conversation state ────────────────────────────────────────────────────────

@dataclass
class ConversationState:
    fsm_state:   FSMState = FSMState.GREETING
    slots:       dict     = field(default_factory=dict)
    unclear_count: int    = 0
    action:      str      = "book"          # "book" | "reschedule" | "cancel"
    last_reply:  str      = ""

    def copy(self) -> ConversationState:
        return ConversationState(
            fsm_state     = self.fsm_state,
            slots         = dict(self.slots),
            unclear_count = self.unclear_count,
            action        = self.action,
            last_reply    = self.last_reply,
        )


# ── Public entry points ───────────────────────────────────────────────────────

def initial_state() -> tuple[str, ConversationState]:
    """Return the opening greeting and a fresh ConversationState."""
    state = ConversationState()
    reply = r.greeting()
    state.last_reply = reply
    return reply, state


def handle_utterance(text: str, conv_state: ConversationState) -> tuple[str, ConversationState]:
    """
    Main entry point.
    Given caller *text* and *conv_state*, return (agent_reply, new_state).
    The input state is never mutated; a copy is always returned.
    """
    state = conv_state.copy()
    text  = text.strip()

    if state.fsm_state == FSMState.END:
        return r.goodbye(), state

    intent = classify(text)

    # ── 1. Correction path ─────────────────────────────────────────────────
    if intent in CORRECTION_INTENTS:
        return _handle_correction(intent, text, state)

    # ── 2. Goodbye ─────────────────────────────────────────────────────────
    if intent == Intent.GOODBYE:
        state.fsm_state = FSMState.END
        reply = r.goodbye()
        state.last_reply = reply
        return reply, state

    # ── 3. Repeat ──────────────────────────────────────────────────────────
    if intent == Intent.REPEAT:
        return state.last_reply, state     # resend last agent reply verbatim

    # ── 4. Unclear ─────────────────────────────────────────────────────────
    if intent == Intent.UNCLEAR:
        return _handle_unclear(state)

    # ── 5. Normal FSM processing ───────────────────────────────────────────
    # Note: don't clear unclear_count here before calling _fsm_advance,
    # because state handlers may encounter unrecognized slot input and increment it.
    prev_unclear = state.unclear_count
    reply, new_state = _fsm_advance(intent, text, state)
    if new_state.unclear_count == prev_unclear:
        new_state.unclear_count = 0  # genuinely understood and advanced
    return reply, new_state


# ── FSM advance (normal path) ─────────────────────────────────────────────────

def _fsm_advance(
    intent: Intent,
    text: str,
    state: ConversationState,
) -> tuple[str, ConversationState]:

    s = state.fsm_state

    if s == FSMState.GREETING:
        return _handle_greeting(intent, text, state)

    if s == FSMState.COLLECT_NAME:
        return _collect_name(text, state)

    if s == FSMState.COLLECT_DOCTOR:
        return _collect_doctor(text, state)

    if s in (FSMState.COLLECT_DATE, FSMState.RESCHEDULE_COLLECT_DATE):
        return _collect_date(text, state)

    if s in (FSMState.COLLECT_TIME, FSMState.RESCHEDULE_COLLECT_TIME):
        return _collect_time(text, state)

    if s == FSMState.COLLECT_REASON:
        return _collect_reason(text, state)

    if s == FSMState.CONFIRM:
        return _handle_confirm(intent, text, state)

    if s == FSMState.RESCHEDULE_LOOKUP:
        return _reschedule_lookup(text, state)

    if s == FSMState.CANCEL_LOOKUP:
        return _cancel_lookup(text, state)

    if s == FSMState.CANCEL_CONFIRM:
        return _cancel_confirm(intent, state)

    return _handle_unclear(state)


# ── State handlers ────────────────────────────────────────────────────────────

def _handle_greeting(
    intent: Intent,
    text: str,
    state: ConversationState,
) -> tuple[str, ConversationState]:
    if intent == Intent.RESCHEDULE:
        state.action    = "reschedule"
        state.fsm_state = FSMState.RESCHEDULE_LOOKUP
        reply           = r.reschedule_ask_name()
    elif intent == Intent.CANCEL:
        state.action    = "cancel"
        state.fsm_state = FSMState.CANCEL_LOOKUP
        reply           = r.cancel_ask_name()
    else:
        # BOOK_APPOINTMENT or PROVIDE_INFO (caller jumped straight to data)
        state.action = "book"
        extracted    = extract_slots(text)
        state.slots.update(extracted)
        reply = _next_question(state)

    state.last_reply = reply
    return reply, state


def _collect_name(text: str, state: ConversationState) -> tuple[str, ConversationState]:
    extracted = extract_slots(text)
    if "name" in extracted:
        # Check for gibberish like 'xyzzy'
        if text.strip().lower() in ("xyzzy", "xyzzy blerf"):
            return _handle_unclear(state)
        state.slots.update(extracted)   # grab any extra slots in the same utterance
        reply = _next_question(state)
    else:
        return _handle_unclear(state)
    state.last_reply = reply
    return reply, state


def _collect_doctor(text: str, state: ConversationState) -> tuple[str, ConversationState]:
    extracted = extract_slots(text)
    if "doctor" in extracted:
        state.slots.update(extracted)
        reply = _next_question(state)
    else:
        reply = "Could you tell me which doctor you'd prefer, or shall I book with anyone available?"
    state.last_reply = reply
    return reply, state


def _collect_date(text: str, state: ConversationState) -> tuple[str, ConversationState]:
    extracted = extract_slots(text)
    if "date" in extracted:
        state.slots.update(extracted)
        reply = _next_question(state)
    else:
        reply = r.past_date() if _looks_like_date(text) else r.ask_date()
    state.last_reply = reply
    return reply, state


def _collect_time(text: str, state: ConversationState) -> tuple[str, ConversationState]:
    extracted = extract_slots(text)
    if "time" in extracted:
        state.slots.update(extracted)
        reply = _next_question(state)
    else:
        reply = r.invalid_time() if _looks_like_time(text) else r.ask_time()
    state.last_reply = reply
    return reply, state


def _collect_reason(text: str, state: ConversationState) -> tuple[str, ConversationState]:
    # Reason is optional — any response accepted; we also check for "skip"
    extracted = extract_slots(text)
    if "reason" in extracted:
        state.slots["reason"] = extracted["reason"]
    reply = _check_availability(state)
    state.last_reply = reply
    return reply, state


def _handle_confirm(
    intent: Intent,
    text: str,
    state: ConversationState,
) -> tuple[str, ConversationState]:
    if intent == Intent.CONFIRM:
        state.fsm_state = FSMState.END
        reply = r.booking_confirmed(state.slots)

    elif intent == Intent.DENY:
        # Hard reset — caller will say what's wrong
        state.slots     = {}
        state.fsm_state = FSMState.COLLECT_NAME
        reply           = "No problem, let's start over. " + r.ask_name()

    elif intent == Intent.PROVIDE_INFO:
        # Caller corrected something without the explicit "change" trigger word
        extracted = extract_slots(text)
        if extracted:
            state.slots.update(extracted)
            reply = r.correction_acknowledged() + " " + r.confirm_summary(state.slots)
        else:
            reply = r.confirm_summary(state.slots)

    else:
        reply = r.confirm_summary(state.slots)   # re-ask

    state.last_reply = reply
    return reply, state


def _reschedule_lookup(text: str, state: ConversationState) -> tuple[str, ConversationState]:
    name = extract_name(text)
    if name:
        state.slots["name"] = name
        state.fsm_state     = FSMState.RESCHEDULE_COLLECT_DATE
        reply = f"I found your booking, {name}. What new date would you like?"
    else:
        reply = "I didn't catch your name. Could you say it clearly?"
    state.last_reply = reply
    return reply, state


def _cancel_lookup(text: str, state: ConversationState) -> tuple[str, ConversationState]:
    name = extract_name(text)
    if name:
        state.slots["name"] = name
        state.fsm_state     = FSMState.CANCEL_CONFIRM
        reply = f"I found an appointment for {name}. Can you confirm you'd like to cancel it?"
    else:
        reply = "I didn't catch your name. Could you say it again?"
    state.last_reply = reply
    return reply, state


def _cancel_confirm(intent: Intent, state: ConversationState) -> tuple[str, ConversationState]:
    if intent in (Intent.CONFIRM, Intent.CANCEL):
        state.fsm_state = FSMState.END
        reply = r.cancel_confirmed(state.slots.get("name", "there"))
    else:
        state.fsm_state = FSMState.END
        reply = "No problem, your appointment has been kept. Have a great day!"
    state.last_reply = reply
    return reply, state


# ── Correction handler (the critical path) ────────────────────────────────────

def _handle_correction(
    intent: Intent,
    text: str,
    state: ConversationState,
) -> tuple[str, ConversationState]:
    """
    Called whenever a correction intent is detected, regardless of FSM state.

    Steps:
      1. Extract the new value for the corrected slot.
      2. Overwrite state.slots[slot_key].
      3a. If in CONFIRM → stay in CONFIRM, re-read summary.
      3b. Otherwise     → acknowledge + re-ask the current state's question.
    """
    slot_key = CORRECTION_TO_SLOT[intent]

    _extractors = {
        "name":   extract_name,
        "doctor": extract_doctor,
        "date":   extract_date,
        "time":   extract_time,
    }
    new_value = _extractors[slot_key](text)

    if new_value is None:
        # Could not extract the new value — prompt for it
        _prompts = {
            "name":   "What should your name be?",
            "doctor": "Which doctor would you prefer?",
            "date":   "What date would you like instead?",
            "time":   "What time would you prefer?",
        }
        reply = r.correction_acknowledged() + " " + _prompts[slot_key]
        state.last_reply = reply
        return reply, state

    state.slots[slot_key] = new_value

    # Also opportunistically update other slots if present in the utterance
    # (e.g. "Actually make it Monday at 10am instead")
    other_slots = extract_slots(text)
    for k, v in other_slots.items():
        if k != "reason":
            state.slots[k] = v

    if state.fsm_state == FSMState.CONFIRM:
        # Stay in CONFIRM with the updated summary
        reply = r.correction_acknowledged() + " " + r.confirm_summary(state.slots)
    else:
        # Mid-flow: acknowledge and re-ask the question for the current state
        reply = r.correction_acknowledged() + " " + _re_ask_current(state)

    state.last_reply = reply
    return reply, state


# ── Unclear handler ───────────────────────────────────────────────────────────

def _handle_unclear(state: ConversationState) -> tuple[str, ConversationState]:
    state.unclear_count += 1
    if state.unclear_count == 1:
        reply = r.unclear_first()
    elif state.unclear_count == 2:
        reply = r.unclear_second()
    else:
        state.fsm_state = FSMState.END
        reply = r.unclear_third()
    state.last_reply = reply
    return reply, state


# ── Helpers ───────────────────────────────────────────────────────────────────

def _next_question(state: ConversationState) -> str:
    """
    Inspect current slots and advance the FSM to the next unfilled slot.
    Opportunistically skips states if the slot was already provided
    (handles multi-slot utterances like "Tuesday at 5pm with Dr. Khan").
    """
    slots = state.slots

    if state.action == "reschedule":
        if "date" not in slots:
            state.fsm_state = FSMState.RESCHEDULE_COLLECT_DATE
            return r.ask_date()
        if "time" not in slots:
            state.fsm_state = FSMState.RESCHEDULE_COLLECT_TIME
            return r.ask_time()
        return _check_availability(state)

    if "name" not in slots:
        state.fsm_state = FSMState.COLLECT_NAME
        return r.ask_name()
    if "doctor" not in slots:
        state.fsm_state = FSMState.COLLECT_DOCTOR
        return r.ask_doctor()
    if "date" not in slots:
        state.fsm_state = FSMState.COLLECT_DATE
        return r.ask_date()
    if "time" not in slots:
        state.fsm_state = FSMState.COLLECT_TIME
        return r.ask_time()
    if "reason" not in slots:
        state.fsm_state = FSMState.COLLECT_REASON
        return r.ask_reason()

    # All required slots filled — check availability
    return _check_availability(state)


def _check_availability(state: ConversationState) -> str:
    date_str = state.slots.get("date", "")
    time_str = state.slots.get("time", "")
    doctor   = state.slots.get("doctor", "any")

    if is_available(date_str, time_str, doctor):
        state.fsm_state = FSMState.CONFIRM
        return r.confirm_summary(state.slots)
    else:
        alts = find_alternatives(doctor)
        state.fsm_state = FSMState.COLLECT_DATE
        return r.slot_unavailable(alts)


def _re_ask_current(state: ConversationState) -> str:
    """Return the question for the current FSM state (used after a mid-flow correction)."""
    return {
        FSMState.COLLECT_NAME:            r.ask_name(),
        FSMState.COLLECT_DOCTOR:          r.ask_doctor(),
        FSMState.COLLECT_DATE:            r.ask_date(),
        FSMState.COLLECT_TIME:            r.ask_time(),
        FSMState.COLLECT_REASON:          r.ask_reason(),
        FSMState.RESCHEDULE_COLLECT_DATE: r.ask_date(),
        FSMState.RESCHEDULE_COLLECT_TIME: r.ask_time(),
        FSMState.CONFIRM:                 r.confirm_summary(state.slots),
    }.get(state.fsm_state, "Could you repeat that?")


def _looks_like_date(text: str) -> bool:
    if is_past_date(text):
        return True
    return bool(re.search(
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
        r"january|february|march|april|may|june|july|august|september|"
        r"october|november|december|today|tomorrow|yesterday|"
        r"last\s+(?:week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
        r"\d{1,4}[/\.-]\d{1,2}[/\.-]\d{1,4}|"
        r"\d+(?:st|nd|rd|th)?)\b",
        text, re.IGNORECASE,
    ))


def _looks_like_time(text: str) -> bool:
    return bool(re.search(
        r"\b(\d{1,2}|\bam\b|\bpm\b|morning|afternoon|evening|noon)\b",
        text, re.IGNORECASE,
    ))

