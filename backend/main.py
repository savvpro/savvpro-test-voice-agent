"""
FastAPI app — exposes the brain over HTTP for the Next.js frontend.

Endpoints
---------
POST /api/chat
    Body: {"session_id"?: str, "text": str}
    Returns: {session_id, text, state, slots, intent, decision, end_call, booking_id, history}

POST /api/reset
    Body: {"session_id": str}
    Returns: {session_id, state: "greeting", slots: {...}}

GET  /api/health
    Returns: {ok: true, version, bookings_count}

GET  /api/sessions/{session_id}
    Returns: full session state (for debugging / the dev panel)

The frontend talks to this server via the gateway using
`?XTransformPort=8000` on every request.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .brain import DM, State, Session
from .sessions import SESSIONS


VERSION = "1.0.0"

app = FastAPI(
    title="SavvPro Voice Agent — Restaurant Booking Brain",
    version=VERSION,
    description="Rule-based (no LLM) voice agent that books tables at a fake restaurant.",
)

# Allow the Next.js dev server to call us. The browser origin will be the
# sandbox gateway; allowing all origins is fine for a demo and means we
# don't need to track every preview URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="Existing session id, or omit to start fresh")
    text: str = Field(..., min_length=0, max_length=2000, description="Caller's transcribed utterance")


class ChatResponse(BaseModel):
    session_id: str
    text: str
    state: str
    slots: dict
    intent: str
    decision: str
    end_call: bool
    booking_id: Optional[str] = None
    history: list = []


class ResetRequest(BaseModel):
    session_id: Optional[str] = None


class ResetResponse(BaseModel):
    session_id: str
    state: str
    slots: dict
    last_prompt: str


class HealthResponse(BaseModel):
    ok: bool
    version: str
    bookings_count: int
    sessions_count: int
    server_time: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> HealthResponse:
    from .brain.restaurant import STORE
    return HealthResponse(
        ok=True,
        version=VERSION,
        bookings_count=len(STORE.bookings),
        sessions_count=len(SESSIONS.all_()),
        server_time=datetime.now().isoformat(),
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.text or not req.text.strip():
        # Empty input — treat as silence
        session = SESSIONS.get_or_create(req.session_id)
        result = DM.process("", session)
    else:
        session = SESSIONS.get_or_create(req.session_id)
        result = DM.process(req.text, session)

    return ChatResponse(
        session_id=session.session_id,
        text=result.text,
        state=result.state,
        slots=result.slots,
        intent=result.intent,
        decision=result.decision,
        end_call=result.end_call,
        booking_id=result.booking_id,
        history=session.history[-20:],
    )


@app.post("/api/reset", response_model=ResetResponse)
def reset(req: ResetRequest) -> ResetResponse:
    if req.session_id:
        session = SESSIONS.reset(req.session_id)
    else:
        session = SESSIONS.new()
    # Seed the greeting so the frontend has a prompt to display/speak
    session.last_prompt = "Thanks for calling The Copper Spoon. I can help you book a table. What day would you like to come in?"
    session.state = State.GREETING
    return ResetResponse(
        session_id=session.session_id,
        state=session.state,
        slots=dict(session.slots),
        last_prompt=session.last_prompt,
    )


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    s: Optional[Session] = SESSIONS.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return s.to_dict()


# ---------------------------------------------------------------------------
# Allow `python -m backend.main` to run the server.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload="--reload" in os.sys.argv,
        log_level="info",
    )
