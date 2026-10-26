"""Session model — expanded for the state machine (Step 7).

Contains:
- ``DialogueState`` enum — the 13 dialogue states.
- ``SlotMap`` — all collected caller information.
- ``Turn`` — one turn of conversation history.
- ``DecisionTrace`` — debugging breadcrumbs for each turn.
- ``Session`` — the caller's conversation session.
"""

from __future__ import annotations

import enum
import threading
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DialogueState(str, enum.Enum):
    """The explicit dialogue states used by the assistant."""

    GREETING = "GREETING"
    COLLECT_TRACKING_ID = "COLLECT_TRACKING_ID"
    CONFIRM_TRACKING_ID = "CONFIRM_TRACKING_ID"
    VERIFY_PHONE = "VERIFY_PHONE"
    CHOOSE_ACTION = "CHOOSE_ACTION"
    COLLECT_DATE = "COLLECT_DATE"
    COLLECT_PERIOD = "COLLECT_PERIOD"
    CONFIRM_SLOT = "CONFIRM_SLOT"
    COLLECT_PICKUP_POINT = "COLLECT_PICKUP_POINT"
    CONFIRM_PICKUP = "CONFIRM_PICKUP"
    CONFIRM_CANCEL = "CONFIRM_CANCEL"
    DELIVER_STATUS = "DELIVER_STATUS"
    ANYTHING_ELSE = "ANYTHING_ELSE"
    END = "END"


class SlotMap(BaseModel):
    """All collected caller information.

    Slots are mutable; the slot filler and state machine update them.
    """

    tracking_id: str | None = None
    ambiguous_ids: list[str] = Field(default_factory=list)
    phone_last4: str | None = None
    intended_date: date | None = None
    intended_period: str | None = None
    confirmed_slot_id: str | None = None
    pickup_point_id: str | None = None
    action_intent: str | None = None
    cancel_confirmed: bool = False

    # Verification flag.
    verified: bool = False


class DecisionTrace(BaseModel):
    """Debugging breadcrumbs for a single turn."""

    intent: str | None = None
    intent_confidence: float | None = None
    runner_up: str | None = None
    runner_up_confidence: float | None = None
    slots_extracted: dict[str, object] = Field(default_factory=dict)
    state_before: str | None = None
    state_after: str | None = None
    rejection_reason: str | None = None


class Turn(BaseModel):
    """One turn of conversation history."""

    role: str  # "user" or "assistant"
    text: str
    trace: DecisionTrace | None = None


class Session(BaseModel):
    """A caller's conversation session.

    The ``lock`` field serialises concurrent turns for the same session.
    It is excluded from JSON serialisation.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    created_at: datetime
    ended: bool = False
    state: DialogueState = DialogueState.GREETING
    slots: SlotMap = Field(default_factory=SlotMap)
    history: list[Turn] = Field(default_factory=list)
    last_assistant_reply: str = ""

    # Counters.
    silence_count: int = 0
    unknown_count: int = 0
    handoff_confirmation_pending: bool = False
    tracking_attempts: int = 0
    phone_attempts: int = 0

    # Per-session threading lock — excluded from serialisation.
    lock: threading.Lock = Field(
        default_factory=threading.Lock,
        exclude=True,
        repr=False,
    )
