"""Request/response models for the booking API."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DialogueState(str, Enum):
    GREETING = "greeting"
    ASK_DATE = "ask_date"
    ASK_TIME = "ask_time"
    ASK_PARTY = "ask_party"
    CONFIRM = "confirm"
    BOOKED = "booked"
    GOODBYE = "goodbye"
    CANCELLED = "cancelled"


class Slots(BaseModel):
    date: Optional[str] = None  # YYYY-MM-DD
    time: Optional[str] = None  # HH:MM 24h
    party_size: Optional[int] = None
    guest_name: Optional[str] = None


class DecisionTrace(BaseModel):
    """What the brain did on this turn — shown in the UI."""

    state_before: str
    state_after: str
    intent: str
    slots_updated: dict[str, Any] = Field(default_factory=dict)
    action: str
    notes: list[str] = Field(default_factory=list)


class Booking(BaseModel):
    id: str
    restaurant: str = "Harbor Lights Bistro"
    date: str
    time: str
    party_size: int
    guest_name: Optional[str] = None
    table_label: str
    status: str = "active"
    created_at: Optional[str] = None


class ConfirmationTicket(BaseModel):
    """Printable confirmation card after a successful booking."""

    code: str
    restaurant: str
    datetime_display: str
    date: str
    time: str
    party_size: int
    table_label: str
    guest_name: Optional[str] = None
    notification_logged: bool = False


class TurnRequest(BaseModel):
    session_id: str
    text: str


class TurnResponse(BaseModel):
    reply: str
    state: str
    slots: Slots
    decision: DecisionTrace
    booking: Optional[Booking] = None
    confirmation: Optional[ConfirmationTicket] = None
    alternatives: list[str] = Field(default_factory=list)


class ResetRequest(BaseModel):
    session_id: str


class SessionSnapshot(BaseModel):
    session_id: str
    state: str
    slots: Slots
    booking: Optional[Booking] = None


class AdminAuth(BaseModel):
    password: str


class BookingListResponse(BaseModel):
    bookings: list[Booking]


class OpenSlotsResponse(BaseModel):
    date: str
    party_size: int
    open_times: list[str]


class AdminStats(BaseModel):
    total_active: int
    total_cancelled: int
    today_count: int
    today_seats: int
    today: str


class SeedResponse(BaseModel):
    ok: bool
    created: int
    ids: list[str]
