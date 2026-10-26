from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Intent(StrEnum):
    CREATE = "CREATE_BOOKING"
    AVAILABILITY = "CHECK_AVAILABILITY"
    RESCHEDULE = "RESCHEDULE_BOOKING"
    CANCEL = "CANCEL_BOOKING"
    INFO = "ASK_BUSINESS_INFO"
    CONFIRM = "CONFIRM"
    DENY = "DENY"
    MODIFY = "MODIFY_DETAILS"
    REPEAT = "REPEAT"
    END = "END_CONVERSATION"
    UNKNOWN = "UNKNOWN"


class State(StrEnum):
    IDLE = "IDLE"
    COLLECTING = "COLLECTING_DETAILS"
    CHECKING = "CHECKING_AVAILABILITY"
    CONFIRMING = "AWAITING_CONFIRMATION"
    BOOKED = "BOOKING_COMPLETE"
    IDENTIFYING = "IDENTIFYING_EXISTING_BOOKING"
    RESCHEDULING = "RESCHEDULING"
    CANCELLING = "CANCELLING"
    COMPLETED = "COMPLETED"


class Entities(BaseModel):
    service: str | None = None
    date: str | None = None
    time: str | None = None
    name: str | None = None
    reference: str | None = None
    period: str | None = None


class Decision(BaseModel):
    intent: Intent
    extracted_entities: dict = Field(default_factory=dict)
    previous_state: State
    current_state: State
    matched_rule: str
    explanation: str
    next_action: str
    missing_information: list[str] = Field(default_factory=list)


class Message(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class AppointmentView(BaseModel):
    reference: str
    service: str
    service_name: str
    customer_name: str
    starts_at: str
    ends_at: str
    timezone: str
    status: str
    version: int


class SessionView(BaseModel):
    id: str
    state: State = State.IDLE
    current_intent: Intent = Intent.UNKNOWN
    entities: Entities = Field(default_factory=Entities)
    missing_information: list[str] = Field(default_factory=list)
    proposed_action: str | None = None
    last_committed_action: str | None = None
    history: list[Message] = Field(default_factory=list)
    last_decision: Decision | None = None
    clarification_count: int = 0
    reply: str = "Welcome to Northline Studio. I can book, check availability, reschedule, or cancel an appointment. How can I help?"
    appointment: AppointmentView | None = None
    last_booking_reference: str | None = None
    target_version: int | None = None
    available_slots: list[str] = Field(default_factory=list)
    revision: int = 0


class TurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1000)
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    expected_revision: int = Field(ge=0)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Say or type a message before sending.")
        return value.strip()
