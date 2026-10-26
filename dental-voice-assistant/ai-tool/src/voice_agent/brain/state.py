"""Brain state machine states and SessionContext dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from voice_agent.ports import SlotInfo


class State(StrEnum):
    START = "START"
    COLLECT_SERVICE = "COLLECT_SERVICE"
    COLLECT_DATE = "COLLECT_DATE"
    COLLECT_TIME = "COLLECT_TIME"
    CLARIFY_TIME = "CLARIFY_TIME"
    OFFER_ALTERNATIVES = "OFFER_ALTERNATIVES"
    COLLECT_NAME = "COLLECT_NAME"
    COLLECT_PHONE = "COLLECT_PHONE"
    CONFIRM_PHONE = "CONFIRM_PHONE"
    CONFIRM_BOOKING = "CONFIRM_BOOKING"
    BOOKED = "BOOKED"

    CANCEL_LOOKUP_PHONE = "CANCEL_LOOKUP_PHONE"
    CANCEL_SELECT_APPT = "CANCEL_SELECT_APPT"
    CANCEL_CONFIRM = "CANCEL_CONFIRM"
    CANCELLED = "CANCELLED"

    RESCHEDULE_LOOKUP_PHONE = "RESCHEDULE_LOOKUP_PHONE"
    RESCHEDULE_SELECT_APPT = "RESCHEDULE_SELECT_APPT"
    RESCHEDULE_COLLECT_NEW_SLOT = "RESCHEDULE_COLLECT_NEW_SLOT"
    RESCHEDULE_OFFER_ALTERNATIVES = "RESCHEDULE_OFFER_ALTERNATIVES"
    RESCHEDULE_CONFIRM = "RESCHEDULE_CONFIRM"
    RESCHEDULED = "RESCHEDULED"

    HANDOFF = "HANDOFF"
    END = "END"


@dataclass
class SessionContext:
    """Carries conversation memory and slot values across turns."""

    session_id: str = "default_session"
    state: State = State.START
    intent: str | None = None

    # Extracted booking slots
    service: str | None = None
    date: date | None = None
    time: time | None = None

    # Ambiguity and alternative tracking
    candidate_time_hour: int | None = None
    offered_slots: list[SlotInfo] = field(default_factory=list)

    # Caller details
    patient_name: str | None = None
    patient_phone: str | None = None
    phone_confirmed: bool = False

    # Existing bookings (for cancel & reschedule)
    user_appointments: list[tuple[str, SlotInfo]] = field(default_factory=list)
    selected_appointment_id: str | None = None
    selected_slot: SlotInfo | None = None
    new_slot: SlotInfo | None = None

    # Guardrails
    fail_count: int = 0
    turn_count: int = 0
    max_turns: int = 40

    def reset_fail_count(self) -> None:
        self.fail_count = 0

    def increment_fail_count(self) -> int:
        self.fail_count += 1
        return self.fail_count
