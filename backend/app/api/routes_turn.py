from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from app.api.deps import get_conversation
from app.schemas import TextTurnRequest, TurnResponse
from app.services.conversation import AudioNotUnderstoodError, SpeechUnavailableError
from app.services.session_store import SessionNotFoundError

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

BAD_BODY = 'send JSON {"text": "..."} or a multipart audio file'


@router.post(
    "/{session_id}/turn",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {"schema": TextTurnRequest.model_json_schema()},
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {"audio": {"type": "string", "format": "binary"}},
                        "required": ["audio"],
                    }
                },
            }
        }
    },
)
async def take_turn(session_id: str, request: Request) -> TurnResponse:
    """One caller turn: JSON ``{"text": ...}`` or a multipart ``audio`` file (webm/ogg/wav)."""
    text: str | None = None
    audio: bytes | None = None
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("audio")
        if upload is None or isinstance(upload, str):
            raise HTTPException(422, "multipart request needs an 'audio' file")
        audio = await upload.read()
    else:
        try:
            text = TextTurnRequest.model_validate_json(await request.body()).text
        except ValidationError:
            raise HTTPException(422, BAD_BODY) from None

    conversation = get_conversation(request)
    try:
        # STT, NLU and the DB are blocking: keep them off the event loop.
        return await run_in_threadpool(conversation.turn, session_id, text=text, audio=audio)
    except SessionNotFoundError:
        raise HTTPException(404, "session not found or expired") from None
    except SpeechUnavailableError as exc:
        raise HTTPException(503, str(exc)) from None
    except AudioNotUnderstoodError as exc:
        raise HTTPException(422, str(exc)) from None
