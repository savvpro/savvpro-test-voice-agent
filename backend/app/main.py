from __future__ import annotations

import logging
from threading import RLock
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.booking import BookingStore
from app.conversation.engine import (
    ConversationEngine,
    SessionExpiredError,
    SessionTerminalError,
    StaleTurnError,
)
from app.conversation.models import Session

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("voice-agent")
app = FastAPI(title="Deterministic Service Booking Assistant")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
store = BookingStore()
engine = ConversationEngine(store)
sessions: dict[str, Session] = {}
sessions_lock = RLock()


class TurnRequest(BaseModel):
    turn_id: str = Field(min_length=1, max_length=100)
    expected_version: int = Field(ge=0)
    transcript: str = Field(max_length=1000)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/conversations", status_code=201)
def create_conversation() -> dict:
    conversation_id = str(uuid4())
    session = engine.create_session(conversation_id)
    with sessions_lock:
        sessions[conversation_id] = session
    return engine.greeting(session)


@app.post("/api/conversations/{conversation_id}/turns")
def submit_turn(conversation_id: str, body: TurnRequest) -> dict:
    with sessions_lock:
        session = sessions.get(conversation_id)
        if not session:
            raise HTTPException(404, "conversation_not_found")
        try:
            response = engine.turn(session, body.turn_id, body.expected_version, body.transcript)
        except StaleTurnError as exc:
            raise HTTPException(409, "stale_turn") from exc
        except SessionExpiredError as exc:
            raise HTTPException(410, "session_expired") from exc
        except SessionTerminalError as exc:
            raise HTTPException(409, "session_terminal") from exc
    logger.info(
        "conversation=%s turn=%s action=%s status=%s",
        conversation_id,
        body.turn_id,
        response["action"],
        response["status"],
    )
    return response


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict:
    session = sessions.get(conversation_id)
    if not session:
        raise HTTPException(404, "conversation_not_found")
    return engine._response(session, "inspect", "session_read", "")


@app.get("/api/bookings/{confirmation_number}")
def get_booking(confirmation_number: str) -> dict:
    booking = next((item for item in store.bookings if item["confirmation_number"] == confirmation_number), None)
    if not booking:
        raise HTTPException(404, "booking_not_found")
    return {key: value for key, value in booking.items() if key != "phone"}
