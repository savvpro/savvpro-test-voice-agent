"""API route definitions."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.database import IdempotencyConflictError
from app.models.schemas import (
    ConversationMessageRequest, ConversationResponse, HealthResponse, ReservationInfo,
)
from app.services.conversations import (
    ConversationReply, ConversationService, MessageConflictError,
    StorageUnavailableError, UnknownSessionError,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Return the current health status of the service."""
    return HealthResponse(
        status="healthy",
        service="voice-assistant-api",
        version="0.1.0",
    )


def conversation_service(request: Request) -> ConversationService:
    return request.app.state.conversation_service


def conversation_response(reply: ConversationReply) -> ConversationResponse:
    return ConversationResponse(
        message=reply.message, session_id=reply.session_id, status=reply.status,
        collected_data=reply.collected_data,
        reservation=ReservationInfo.model_validate(reply.reservation) if reply.reservation else None,
    )


@router.post("/conversations/start", response_model=ConversationResponse, status_code=201)
def start_conversation(service: ConversationService = Depends(conversation_service)):
    return conversation_response(service.start_conversation())


@router.post("/conversations/message", response_model=ConversationResponse)
def process_message(
    body: ConversationMessageRequest,
    service: ConversationService = Depends(conversation_service),
):
    try:
        reply = service.process_message(body.session_id, body.message, body.request_id)
    except UnknownSessionError:
        raise HTTPException(404, "Unknown conversation. Start a new conversation.") from None
    except MessageConflictError:
        raise HTTPException(409, "This request_id was already used with different text.") from None
    except IdempotencyConflictError:
        raise HTTPException(409, "Unable to reconcile this booking. Retry the original confirmation.") from None
    except StorageUnavailableError:
        logger.exception("Reservation storage operation failed")
        raise HTTPException(
            503, "Reservation storage is temporarily unavailable. "
            "The booking result could not be verified. Please retry the same request.",
        ) from None
    except Exception:
        logger.exception("Unexpected conversation processing failure")
        raise HTTPException(500, "Unable to process this message. Please retry the same request.") from None
    return conversation_response(reply)
