"""API routes for the voice assistant backend.

Provides both REST endpoints and a WebSocket for real-time conversation.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from brain.engine import DialogEngine

logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton dialog engine shared across requests
engine = DialogEngine()


@router.get("/api/tts")
async def text_to_speech(text: str):
    """Generate audio for the given text using native system TTS."""
    cleaned = text.replace("*", "").replace("#", "").replace("_", "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Text is required")

    say_bin = shutil.which("say")
    if say_bin:
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            subprocess.run(
                [say_bin, "-v", "Samantha", "-o", tmp_path, cleaned],
                check=True,
                capture_output=True,
            )
            return FileResponse(tmp_path, media_type="audio/mp4")
        except Exception as e:
            logger.warning(f"say command failed, retrying with default voice: {e}")
            try:
                subprocess.run(
                    [say_bin, "-o", tmp_path, cleaned],
                    check=True,
                    capture_output=True,
                )
                return FileResponse(tmp_path, media_type="audio/mp4")
            except Exception as e2:
                logger.error(f"say default voice also failed: {e2}")
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    raise HTTPException(status_code=501, detail="System TTS engine not available")


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

class MessageRequest(BaseModel):
    """Request body for the /message endpoint."""
    conversation_id: Optional[str] = None
    text: str


class MessageResponse(BaseModel):
    """Response body for the /message endpoint."""
    conversation_id: str
    response: str
    state: dict


@router.post("/api/conversation/start")
async def start_conversation():
    """Start a new conversation and return the greeting."""
    conv_id, greeting, state_info = engine.start_conversation()
    return {
        "conversation_id": conv_id,
        "response": greeting,
        "state": state_info,
    }


@router.post("/api/message", response_model=MessageResponse)
async def send_message(req: MessageRequest):
    """Send a message and get the assistant's response."""
    if not req.conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id is required")

    try:
        response, state_info = engine.process(req.conversation_id, req.text)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return MessageResponse(
        conversation_id=req.conversation_id,
        response=response,
        state=state_info,
    )


@router.get("/api/conversation/{conv_id}")
async def get_conversation(conv_id: str):
    """Get current conversation state."""
    conv = engine.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "conversation_id": conv.id,
        "state": conv.state.value,
        "booking": {
            "id": conv.booking.id,
            "guest_name": conv.booking.guest_name,
            "date": conv.booking.date.isoformat() if conv.booking.date else None,
            "time": conv.booking.time.isoformat() if conv.booking.time else None,
            "party_size": conv.booking.party_size,
            "status": conv.booking.status.value,
        },
        "turns": [
            {"role": t.role, "text": t.text, "state": t.state, "extracted": t.extracted}
            for t in conv.turns
        ],
        "turn_count": conv.turn_count,
    }


@router.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "voice-assistant-backend"}


# ---------------------------------------------------------------------------
# WebSocket endpoint for real-time conversation
# ---------------------------------------------------------------------------

@router.websocket("/ws/conversation")
async def websocket_conversation(websocket: WebSocket):
    """WebSocket endpoint for real-time voice conversation.

    Protocol:
        Client sends: {"type": "start"} or {"type": "message", "text": "..."}
        Server sends: {"type": "response", "text": "...", "state": {...}}
    """
    await websocket.accept()
    conv_id: Optional[str] = None

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type", "")

            if msg_type == "start":
                conv_id, greeting, state_info = engine.start_conversation()
                await websocket.send_json({
                    "type": "response",
                    "conversation_id": conv_id,
                    "text": greeting,
                    "state": state_info,
                })

            elif msg_type == "message" and conv_id:
                user_text = msg.get("text", "").strip()
                if not user_text:
                    continue

                response, state_info = engine.process(conv_id, user_text)
                await websocket.send_json({
                    "type": "response",
                    "conversation_id": conv_id,
                    "text": response,
                    "state": state_info,
                })

            else:
                await websocket.send_json({
                    "type": "error",
                    "text": "Send {\"type\": \"start\"} first.",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: conv=%s", conv_id)
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
        try:
            await websocket.send_json({"type": "error", "text": str(e)})
        except Exception:
            pass
