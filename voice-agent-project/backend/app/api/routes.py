from __future__ import annotations

import logging
import time
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request, Response

from ..brain.models import TurnResult
from .schemas import TraceOut, TurnRequest, TurnResponse

log = logging.getLogger("voice_agent")
router = APIRouter()


def _to_response(result: TurnResult) -> TurnResponse:
    s = result.session
    return TurnResponse(
        session_id=s.id,
        reply=result.reply,
        ended=result.ended,
        state=s.state.value,
        intent=s.intent.value if s.intent else None,
        slots=s.slots.as_dict(),
        trace=TraceOut(**asdict(result.trace)),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/sessions", response_model=TurnResponse, status_code=201)
def create_session(request: Request) -> TurnResponse:
    session = request.app.state.sessions.create()
    result = request.app.state.manager.start(session)
    log.info("session=%s started", session.id)
    return _to_response(result)


@router.post("/api/sessions/{session_id}/turn", response_model=TurnResponse)
def take_turn(session_id: str, body: TurnRequest, request: Request) -> TurnResponse:
    session = request.app.state.sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    started = time.perf_counter()
    result = request.app.state.manager.handle(session, body.text, body.confidence)
    log.info(
        "session=%s turn=%d state=%s->%s rule=%s latency_ms=%.2f",
        session_id, session.turns, result.trace.state_before, result.trace.state_after,
        result.trace.rule, (time.perf_counter() - started) * 1000,
    )  # fmt: skip
    return _to_response(result)


@router.delete("/api/sessions/{session_id}", status_code=204, response_class=Response)
def end_session(session_id: str, request: Request) -> Response:
    request.app.state.sessions.delete(session_id)
    return Response(status_code=204)
