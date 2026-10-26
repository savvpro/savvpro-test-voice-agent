"""Core domain models for Tableline voice agent."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ConversationState(str, Enum):
    IDLE = "IDLE"
    GREETING = "GREETING"
    COLLECTING_DETAILS = "COLLECTING_DETAILS"
    OFFERING_ALTERNATIVES = "OFFERING_ALTERNATIVES"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class BookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class BookingDetails(BaseModel):
    date: Optional[str] = Field(None, description="ISO format date YYYY-MM-DD")
    time: Optional[str] = Field(None, description="24-hour format HH:MM")
    guests: Optional[int] = Field(None, description="Party size (1-12)")
    customer_name: Optional[str] = Field(None, description="Primary contact name")
    special_notes: Optional[str] = Field(None, description="Dietary notes or seating preference")


class AvailabilitySlot(BaseModel):
    time: str
    available: bool
    remaining_tables: int


class ReservationRecord(BaseModel):
    reservation_id: str
    date: str
    time: str
    guests: int
    customer_name: str
    status: BookingStatus = BookingStatus.CONFIRMED
    created_at: str


class ConversationTurnRequest(BaseModel):
    conversation_id: str
    message: str


class ConversationTurnResponse(BaseModel):
    conversation_id: str
    state: ConversationState
    assistant_message: str
    booking_details: BookingDetails
    suggested_alternatives: List[str] = []
    is_confirmed: bool = False
    reservation_reference: Optional[str] = None
    confidence_hint: Optional[str] = None
