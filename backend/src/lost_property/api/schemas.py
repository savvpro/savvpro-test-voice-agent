from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from lost_property.domain.models import (
    Category,
    Fields,
    Message,
    Model,
    OutcomeKind,
    Receipt,
    Stage,
    Trace,
)


class TurnRequest(Model):
    request_id: UUID
    expected_version: int = Field(ge=0)
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class CandidateView(Model):
    label: str
    category: Category
    description: str
    colour: str | None
    score: float
    signals: dict[str, float]


class SessionView(Model):
    version: int
    state: Stage
    reply: str
    fields: Fields
    candidates: list[CandidateView]
    trace: Trace
    transcript: list[Message]
    proposal: OutcomeKind | None
    receipt: Receipt | None
    restart_pending: bool


class ErrorDetail(Model):
    code: str
    message: str
    request_id: str


class ErrorResponse(Model):
    error: ErrorDetail


class Health(Model):
    status: Literal["ok", "ready"]


class Transcription(Model):
    text: str
