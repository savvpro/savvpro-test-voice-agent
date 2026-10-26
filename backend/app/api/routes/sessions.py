"""Session lifecycle and turn processing endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import (
    get_clock,
    get_parcel_repo,
    get_runtime_settings,
    get_session_store,
)
from app.brain.constants import MESSAGES
from app.brain.state_machine import StateMachine
from app.core.config import Settings
from app.data.repository import InMemoryParcelRepository, InMemorySessionStore
from app.models.api import HistoryResponse, SessionResponse, TurnRequest, TurnResponse
from app.models.session import DialogueState, Session, Turn

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _require_session(store: InMemorySessionStore, session_id: str) -> Session:
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    store: Annotated[InMemorySessionStore, Depends(get_session_store)],
    clock: Annotated[datetime, Depends(get_clock)],
) -> SessionResponse:
    session = Session(
        session_id=str(uuid4()),
        created_at=clock,
        state=DialogueState.COLLECT_TRACKING_ID,
    )
    session.history.append(Turn(role="assistant", text=MESSAGES["greeting"]))
    session.last_assistant_reply = MESSAGES["greeting"]
    store.save_session(session)
    return SessionResponse(
        session_id=session.session_id,
        state=session.state.value,
        greeting=MESSAGES["greeting"],
    )


@router.post("/{session_id}/turns", response_model=TurnResponse)
def process_turn(
    session_id: str,
    request: TurnRequest,
    store: Annotated[InMemorySessionStore, Depends(get_session_store)],
    repo: Annotated[InMemoryParcelRepository, Depends(get_parcel_repo)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
    clock: Annotated[datetime, Depends(get_clock)],
) -> TurnResponse:
    session = _require_session(store, session_id)
    with session.lock:
        machine = StateMachine(
            repo,
            max_tracking_attempts=settings.max_tracking_attempts,
            max_phone_attempts=settings.max_phone_attempts,
            max_silence_turns=settings.max_silence_turns,
            max_unknown_turns=settings.max_unknown_turns,
        )
        confidence = request.stt_confidence if request.stt_confidence is not None else 1.0
        result = machine.process(
            session,
            request.text,
            clock,
            silence=request.silence,
            stt_confidence=confidence,
        )
        store.save_session(session)
    return TurnResponse(reply=result.reply, ended=result.ended, trace=result.trace)


@router.get("/{session_id}", response_model=HistoryResponse)
def get_session(
    session_id: str,
    store: Annotated[InMemorySessionStore, Depends(get_session_store)],
) -> HistoryResponse:
    session = _require_session(store, session_id)
    return HistoryResponse(
        session_id=session.session_id,
        state=session.state.value,
        verified=session.slots.verified,
        ended=session.ended,
        slots=session.slots.model_dump(mode="json"),
        turns=session.history,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    store: Annotated[InMemorySessionStore, Depends(get_session_store)],
) -> Response:
    session = _require_session(store, session_id)
    with session.lock:
        store.delete_session(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
