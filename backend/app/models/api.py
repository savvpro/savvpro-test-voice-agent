"""Request and response schemas for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.session import DecisionTrace, Turn


class TurnRequest(BaseModel):
    text: str = Field(default="", max_length=2000)
    silence: bool = False
    stt_confidence: float | None = None


class TurnResponse(BaseModel):
    reply: str
    ended: bool
    trace: DecisionTrace


class SessionResponse(BaseModel):
    session_id: str
    state: str
    greeting: str


class HistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    state: str
    verified: bool
    ended: bool
    slots: dict[str, object]
    turns: list[Turn]
