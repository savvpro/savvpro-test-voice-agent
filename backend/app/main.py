"""FastAPI layer. The browser does speech-to-text / text-to-speech; this API only sees text."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .brain import Brain, Session
from .scheduler import Schedule, seed_demo

MAX_SESSIONS = 500


class TurnRequest(BaseModel):
    text: str = Field(default="", max_length=500)


class TurnResponse(BaseModel):
    reply: str
    state: str
    intent: str | None
    slots: dict
    trace: list[str]
    ended: bool
    alternatives: list[str]


class SessionResponse(BaseModel):
    session_id: str
    reply: str
    state: str


def create_app(brain: Brain | None = None) -> FastAPI:
    app = FastAPI(title="Bright Smile Dental Voice Assistant")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if brain is None:
        schedule = Schedule()
        seed_demo(schedule, datetime.now().date())
        brain = Brain(schedule)
    sessions: dict[str, Session] = {}

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/api/sessions", response_model=SessionResponse)
    def start_session() -> SessionResponse:
        if len(sessions) >= MAX_SESSIONS:          # keep memory bounded in this demo
            sessions.pop(next(iter(sessions)))
        sid = uuid.uuid4().hex
        sessions[sid] = brain.new_session(sid)
        return SessionResponse(session_id=sid, reply=sessions[sid].last_reply, state="start")

    @app.post("/api/sessions/{sid}/turn", response_model=TurnResponse)
    def turn(sid: str, body: TurnRequest) -> TurnResponse:
        session = sessions.get(sid)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        return TurnResponse(**brain.handle(session, body.text).__dict__)

    return app


app = create_app()
