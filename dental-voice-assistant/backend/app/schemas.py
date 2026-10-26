"""Pydantic schemas for WebSocket messaging and REST API payloads."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

# ── Client -> Server WS Messages ─────────────────────────────────────────────


class UserTextMessage(BaseModel):
    """Client sends typed text input."""

    type: Literal["user_text"] = "user_text"
    text: str = Field(..., max_length=1000)


class EndCallMessage(BaseModel):
    """Client explicitly terminates the call."""

    type: Literal["end"] = "end"


ClientMessage = Annotated[
    UserTextMessage | EndCallMessage,
    Field(discriminator="type"),
]


# ── Server -> Client WS Messages ─────────────────────────────────────────────


class TurnMessage(BaseModel):
    """Server sends assistant turn result with audio, reply, and stage timings."""

    type: Literal["turn"] = "turn"
    turn: int = 0
    user_text: str = ""
    reply_text: str
    state: str
    end_call: bool = False
    action: str | None = None
    slots: dict[str, Any] = Field(default_factory=dict)
    audio: str | None = None  # Base64-encoded audio bytes
    audio_mime: str | None = "audio/mpeg"
    timings: dict[str, float] = Field(default_factory=dict)


class ErrorMessage(BaseModel):
    """Server sends error notification before or during call."""

    type: Literal["error"] = "error"
    error: str
    detail: str | None = None


class CallEndedMessage(BaseModel):
    """Server signals call completion / disconnection."""

    type: Literal["call_ended"] = "call_ended"
    reason: str
