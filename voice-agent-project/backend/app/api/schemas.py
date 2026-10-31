from __future__ import annotations

from pydantic import BaseModel, Field


class TurnRequest(BaseModel):
    text: str = Field(default="", max_length=500, description="Caller's words; empty string means silence")
    confidence: float | None = Field(default=None, ge=0, le=1, description="Speech-to-text confidence")


class TraceOut(BaseModel):
    heard: str
    state_before: str
    state_after: str
    intents: list[str]
    entities: dict[str, str]
    rule: str
    notes: list[str]


class TurnResponse(BaseModel):
    session_id: str
    reply: str
    ended: bool
    state: str
    intent: str | None
    slots: dict[str, str | None]
    trace: TraceOut
