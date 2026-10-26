"""Pydantic models for conversation state."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from models.booking import Booking


class ConversationState(str, Enum):
    """All possible states of the dialog state machine."""

    GREETING = "greeting"
    ASK_DATE = "ask_date"
    ASK_TIME = "ask_time"
    ASK_PARTY_SIZE = "ask_party_size"
    ASK_NAME = "ask_name"
    ASK_CONTACT = "ask_contact"
    CHECK_AVAILABILITY = "check_availability"
    SUGGEST_ALTERNATIVE = "suggest_alternative"
    CONFIRM = "confirm"
    BOOKED = "booked"
    GOODBYE = "goodbye"
    CANCELLED = "cancelled"
    ERROR = "error"


class Turn(BaseModel):
    """A single conversation turn."""

    role: str  # "user" or "assistant"
    text: str
    state: Optional[str] = None
    extracted: Optional[dict] = None


class Conversation(BaseModel):
    """Tracks the full conversation context."""

    id: str
    state: ConversationState = ConversationState.GREETING
    booking: Booking = Field(default_factory=Booking)
    turns: List[Turn] = Field(default_factory=list)
    turn_count: int = 0
    modification_count: int = 0

    def add_turn(self, role: str, text: str, extracted: Optional[dict] = None) -> None:
        """Record a turn in the conversation history."""
        self.turns.append(Turn(
            role=role,
            text=text,
            state=self.state.value,
            extracted=extracted,
        ))
        self.turn_count += 1
