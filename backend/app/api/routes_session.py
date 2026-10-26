from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_conversation
from app.schemas import HistoryEntryOut, SessionOut, TurnResponse
from app.services.conversation import ConversationService
from app.services.session_store import SessionNotFoundError

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

Conversation = Annotated[ConversationService, Depends(get_conversation)]


@router.post("", status_code=201)
def create_session(conversation: Conversation) -> TurnResponse:
    """Start a call; the response carries the agent's greeting."""
    return conversation.start()


@router.get("/{session_id}")
def get_session(session_id: str, conversation: Conversation) -> SessionOut:
    try:
        call = conversation.get(session_id)
    except SessionNotFoundError:
        raise HTTPException(404, "session not found or expired") from None
    return SessionOut(
        session_id=call.id,
        ended=call.ended,
        frame=call.frame,
        history=[HistoryEntryOut(role=h.role, text=h.text, at=h.at) for h in call.history],
    )
