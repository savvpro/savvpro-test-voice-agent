"""Conversation engine — finite-state-machine controller for reservations.

The engine is **completely deterministic**: every transition, validation
rule, and response is driven by explicit Python code. No LLM, no
external AI service.

The engine is independent of FastAPI, the database, and the frontend
so it can be tested in isolation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.brain.parser import IntentParser, ParseResult
from app.brain.responses import (
    already_completed,
    ambiguous_time,
    ask_confirmation,
    ask_date,
    ask_party_size,
    ask_party_size_after_time,
    ask_time,
    ask_time_after_date,
    ask_what_to_change,
    booking_confirmed,
    cancelled,
    confirm_details,
    could_not_understand,
    could_not_understand_date,
    could_not_understand_party_size,
    could_not_understand_time,
    greeting,
    help_message,
    invalid_date,
    invalid_date_past,
    invalid_date_too_far,
    invalid_party_size_too_large,
    invalid_party_size_zero,
    invalid_time,
    invalid_time_outside_hours,
    restarted,
)
from app.brain.states import ConversationState, Intent

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

MAX_PARTY_SIZE = 20
MAX_ADVANCE_DAYS = 90
OPENING_TIME = "11:00"   # HH:MM
LAST_SEATING = "21:30"   # HH:MM

# ---------------------------------------------------------------------------
# Session data
# ---------------------------------------------------------------------------


@dataclass
class ConversationSession:
    """Mutable per-conversation state."""

    session_id: str
    state: ConversationState = ConversationState.GREETING
    date: Optional[str] = None
    time: Optional[str] = None
    party_size: Optional[int] = None
    history: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def collected_data(self) -> dict:
        return {
            "date": self.date,
            "time": self.time,
            "party_size": self.party_size,
        }

    def reset_data(self) -> None:
        self.date = None
        self.time = None
        self.party_size = None


# ---------------------------------------------------------------------------
# Engine response
# ---------------------------------------------------------------------------


@dataclass
class EngineResponse:
    """Immutable response returned by the engine to the caller."""

    message: str
    state: str
    collected_data: dict
    session_id: str


# ---------------------------------------------------------------------------
# Conversation engine
# ---------------------------------------------------------------------------


class ConversationEngine:
    """Finite-state-machine engine for restaurant reservation conversations.

    Usage::

        engine = ConversationEngine()
        sid = engine.create_session()
        resp = engine.start_conversation(sid)   # greeting
        resp = engine.process_input(sid, "tomorrow at 7pm for 4")
    """

    def __init__(self, reference_date: Optional[datetime] = None) -> None:
        self._sessions: dict[str, ConversationSession] = {}
        self._parser = IntentParser()
        self._reference_date = reference_date  # pin for testing

    # -- Session management -------------------------------------------------

    def create_session(self, session_id: Optional[str] = None) -> str:
        sid = session_id or uuid.uuid4().hex
        self._sessions[sid] = ConversationSession(session_id=sid)
        return sid

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        return self._sessions.get(session_id)

    # -- Public conversation methods ----------------------------------------

    def start_conversation(self, session_id: str) -> EngineResponse:
        """Return the initial greeting and move to ASK_DATE."""
        session = self._sessions[session_id]
        session.state = ConversationState.ASK_DATE
        msg = greeting()
        self._record(session, "[system]", msg)
        return self._response(session, msg)

    def process_input(self, session_id: str, text: str) -> EngineResponse:
        """Process one turn of user input and return a response."""
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Unknown session: {session_id}")

        self._record(session, text, "")

        result = self._parser.parse(text, self._reference_date)

        # Only an explicit restart may leave a terminal state.
        if (
            result.intent != Intent.RESTART
            and session.state == ConversationState.COMPLETED
        ):
            msg = already_completed()
            self._update_last_response(session, msg)
            return self._response(session, msg)

        if (
            result.intent != Intent.RESTART
            and session.state == ConversationState.CANCELLED
        ):
            msg = cancelled()
            self._update_last_response(session, msg)
            return self._response(session, msg)

        global_resp = self._handle_global(session, result)
        if global_resp is not None:
            return global_resp

        # A requested correction must be resolved before confirmation can resume.
        changes = {
            Intent.CHANGE_DATE: ("date", ConversationState.ASK_DATE),
            Intent.CHANGE_TIME: ("time", ConversationState.ASK_TIME),
            Intent.CHANGE_PARTY_SIZE: ("party_size", ConversationState.ASK_PARTY_SIZE),
        }
        if result.intent in changes:
            field_name, state = changes[result.intent]
            setattr(session, field_name, None)
            session.state = state

        # Validate all provided fields, including corrections, before dispatch.
        errors = self._apply_entities(session, result)
        if errors:
            session.state = errors[0][0]
            msg = " ".join(message for _, message in errors)
            self._update_last_response(session, msg)
            return self._response(session, msg)

        # State-specific handlers
        handler = {
            ConversationState.GREETING: self._handle_greeting,
            ConversationState.ASK_DATE: self._handle_ask_date,
            ConversationState.ASK_TIME: self._handle_ask_time,
            ConversationState.ASK_PARTY_SIZE: self._handle_ask_party_size,
            ConversationState.CONFIRM: self._handle_confirm,
        }.get(session.state)

        if handler:
            msg = handler(session, result)
        else:
            msg = could_not_understand()

        self._update_last_response(session, msg)
        return self._response(session, msg)

    # -- Global intent handlers ---------------------------------------------

    def _handle_global(
        self, session: ConversationSession, result: ParseResult,
    ) -> Optional[EngineResponse]:
        if result.intent == Intent.CANCEL:
            session.state = ConversationState.CANCELLED
            msg = cancelled()
            self._update_last_response(session, msg)
            return self._response(session, msg)

        if result.intent == Intent.RESTART:
            session.reset_data()
            session.state = ConversationState.ASK_DATE
            msg = restarted()
            self._update_last_response(session, msg)
            return self._response(session, msg)

        if result.intent == Intent.HELP:
            msg = help_message()
            self._update_last_response(session, msg)
            return self._response(session, msg)

        return None  # not a global intent

    # -- State handlers -----------------------------------------------------

    def _handle_greeting(
        self, session: ConversationSession, result: ParseResult,
    ) -> str:
        # Any input in the greeting state advances the conversation
        session.state = ConversationState.ASK_DATE
        return self._advance_message(session, result)

    def _handle_ask_date(
        self, session: ConversationSession, result: ParseResult,
    ) -> str:
        if session.date is not None:
            return self._advance_message(session, result)

        if result.intent == Intent.CHANGE_DATE:
            return ask_date()
        return could_not_understand_date()

    def _handle_ask_time(
        self, session: ConversationSession, result: ParseResult,
    ) -> str:
        if session.time is not None:
            return self._advance_message(session, result)

        if result.intent == Intent.CHANGE_TIME:
            return ask_time()
        return could_not_understand_time()

    def _handle_ask_party_size(
        self, session: ConversationSession, result: ParseResult,
    ) -> str:
        if session.party_size is not None:
            return self._advance_message(session, result)

        if result.intent == Intent.CHANGE_PARTY_SIZE:
            return ask_party_size()
        return could_not_understand_party_size()

    def _handle_confirm(
        self, session: ConversationSession, result: ParseResult,
    ) -> str:
        # If user provided new entities, re-confirm
        if any(v is not None for v in (result.date, result.time, result.party_size)):
            return confirm_details(session.date, session.time, session.party_size)

        if result.intent == Intent.DENY:
            return ask_what_to_change()

        if result.intent == Intent.CONFIRM:
            session.state = ConversationState.COMPLETED
            return booking_confirmed(session.date, session.time, session.party_size)

        # Unrelated input in confirm state
        return ask_confirmation()

    # -- Advancing the conversation -----------------------------------------

    def _next_state(self, session: ConversationSession) -> ConversationState:
        """Determine which state to go to based on what data is still missing."""
        if session.date is None:
            return ConversationState.ASK_DATE
        if session.time is None:
            return ConversationState.ASK_TIME
        if session.party_size is None:
            return ConversationState.ASK_PARTY_SIZE
        return ConversationState.CONFIRM

    def _advance_message(
        self, session: ConversationSession, result: ParseResult,
    ) -> str:
        """Move to the next missing-data state and return the prompt."""
        next_st = self._next_state(session)
        session.state = next_st

        if next_st == ConversationState.ASK_DATE:
            return ask_date()
        if next_st == ConversationState.ASK_TIME:
            if session.date:
                return ask_time_after_date(session.date)
            return ask_time()
        if next_st == ConversationState.ASK_PARTY_SIZE:
            if session.time:
                return ask_party_size_after_time(session.time)
            return ask_party_size()
        if next_st == ConversationState.CONFIRM:
            return confirm_details(session.date, session.time, session.party_size)
        return could_not_understand()

    # -- Entity application -------------------------------------------------

    def _apply_entities(
        self, session: ConversationSession, result: ParseResult,
    ) -> list[tuple[ConversationState, str]]:
        """Validate this turn, retaining valid fields and clearing invalid ones.

        Errors belong to this turn rather than the engine, so sessions cannot
        share pending errors. Clearing rejected corrections prevents stale
        values from being confirmed by a later, unrelated reply.
        """
        if result.raw_number is not None:
            if session.state in (ConversationState.GREETING, ConversationState.ASK_DATE):
                ref = self._reference_date or datetime.now()
                today = ref.replace(hour=0, minute=0, second=0, microsecond=0)
                result.date = IntentParser._resolve_day_only(today, result.raw_number)
                if result.date is None:
                    result.date_error = "invalid"
            elif session.state == ConversationState.ASK_TIME:
                hour = result.raw_number
                if 1 <= hour <= 11:
                    hour += 12  # Preserve the restaurant's PM default.
                result.time = f"{hour:02d}:00"
            elif session.state == ConversationState.ASK_PARTY_SIZE:
                result.party_size = result.raw_number

        errors: list[tuple[ConversationState, str]] = []
        fields = (
            ("date", result.date, result.date_error, self._validate_date,
             ConversationState.ASK_DATE),
            ("time", result.time, result.time_error, self._validate_time,
             ConversationState.ASK_TIME),
            ("party_size", result.party_size, None, self._validate_party_size,
             ConversationState.ASK_PARTY_SIZE),
        )
        for name, value, parse_error, validate, state in fields:
            if parse_error:
                if name == "date":
                    message = invalid_date()
                elif parse_error == "ambiguous":
                    message = ambiguous_time()
                else:
                    message = invalid_time()
            elif value is not None:
                valid, message = validate(value)
                if valid:
                    setattr(session, name, value)
                    continue
            else:
                continue

            setattr(session, name, None)
            errors.append((state, message))

        return errors

    # -- Validation ---------------------------------------------------------

    def _validate_date(self, iso_date: str) -> tuple[bool, str]:
        ref = self._reference_date or datetime.now()
        today = ref.replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            dt = datetime.strptime(iso_date, "%Y-%m-%d")
        except ValueError:
            return False, could_not_understand_date()

        if dt < today:
            return False, invalid_date_past()

        if dt > today + timedelta(days=MAX_ADVANCE_DAYS):
            return False, invalid_date_too_far()

        return True, ""

    @staticmethod
    def _validate_time(hhmm: str) -> tuple[bool, str]:
        try:
            parts = hhmm.split(":")
            if len(parts) != 2:
                return False, invalid_time()
            hour, minute = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return False, invalid_time()

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return False, invalid_time()

        time_val = hour * 60 + minute
        open_val = 11 * 60  # 11:00
        close_val = 21 * 60 + 30  # 21:30

        if time_val < open_val or time_val > close_val:
            return False, invalid_time_outside_hours()

        return True, ""

    @staticmethod
    def _validate_party_size(size: int) -> tuple[bool, str]:
        if size < 1:
            return False, invalid_party_size_zero()
        if size > MAX_PARTY_SIZE:
            return False, invalid_party_size_too_large(MAX_PARTY_SIZE)
        return True, ""

    # -- Helpers ------------------------------------------------------------

    def _response(
        self, session: ConversationSession, message: str,
    ) -> EngineResponse:
        return EngineResponse(
            message=message,
            state=session.state.value,
            collected_data=session.collected_data(),
            session_id=session.session_id,
        )

    @staticmethod
    def _record(
        session: ConversationSession, user_text: str, assistant_text: str,
    ) -> None:
        session.history.append({
            "user": user_text,
            "assistant": assistant_text,
        })

    @staticmethod
    def _update_last_response(
        session: ConversationSession, text: str,
    ) -> None:
        if session.history:
            session.history[-1]["assistant"] = text
