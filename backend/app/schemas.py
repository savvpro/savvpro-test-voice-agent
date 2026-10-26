"""Request and response models for the HTTP API."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.dialogue.frame import Frame
from app.dialogue.states import State
from app.nlu.pipeline import NLUResult


class TextTurnRequest(BaseModel):
    # Empty text is allowed: the frontend sends it when the caller stays silent.
    text: str = ""


class DecisionOut(BaseModel):
    state: State
    action: str | None
    frame: Frame
    end_call: bool
    expected_slot: str | None


class Timings(BaseModel):
    stt: float = 0.0
    nlu: float = 0.0
    dm: float = 0.0
    tts: float = 0.0


class TurnResponse(BaseModel):
    session_id: str
    transcript: str | None = Field(description="What the caller said (None on the greeting turn)")
    transcript_confidence: float | None = None
    nlu: NLUResult | None
    decision: DecisionOut
    reply_text: str
    audio_base64: str | None
    audio_mime: str | None
    timings_ms: Timings


class HistoryEntryOut(BaseModel):
    role: Literal["caller", "agent"]
    text: str
    at: dt.datetime


class SessionOut(BaseModel):
    session_id: str
    ended: bool
    frame: Frame
    history: list[HistoryEntryOut]


class SlotOut(BaseModel):
    id: int
    start: dt.datetime
    end: dt.datetime
    doctor: str
    department: str
    is_booked: bool


class AppointmentOut(BaseModel):
    booking_ref: str
    patient_name: str
    phone: str = Field(description="Masked, e.g. 0300****567")
    start: dt.datetime
    doctor: str
    department: str
    status: str


class ErrorOut(BaseModel):
    detail: str


def mask_phone(phone: str) -> str:
    return phone[:4] + "*" * max(len(phone) - 7, 0) + phone[-3:]
