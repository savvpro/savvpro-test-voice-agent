"""Pydantic schemas for API request and response models."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""

    status: str
    service: str
    version: str


Identifier = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=128)]
MessageText = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=2000)]


class ConversationMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: Identifier
    message: MessageText
    request_id: Identifier


class CollectedDetails(BaseModel):
    date: str | None
    time: str | None
    party_size: int | None


class ReservationInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reservation_id: str
    reservation_date: str
    reservation_time: str
    party_size: int
    status: str
    created_at: str


class ConversationResponse(BaseModel):
    message: str
    session_id: str
    status: str
    collected_data: CollectedDetails
    reservation: ReservationInfo | None = None
