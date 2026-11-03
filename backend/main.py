"""
FastAPI WebSocket server for the Voice Agent.

WebSocket: ws://localhost:8000/ws

Protocol
--------
  Client → Server (Text):
      {"type": "text", "text": "<caller utterance>"}
      OR {"text": "<caller utterance>"}
      OR plain string

  Client → Server (Audio chunk / audio file via binary WS or base64):
      Binary frame: raw audio bytes (.wav, .webm, or .ogg)
      OR {"type": "audio", "data": "<base64_encoded_audio>"}

  Server → Client:
      {
          "type": "agent_response",
          "transcription": "<caller recognized text (if audio was sent)>",
          "reply": "<agent reply>",
          "state": "<FSM state name>",
          "slots": {<filled slots>}
      }

  On connect the server immediately sends the opening greeting.
  The connection is closed by the server when FSMState.END is reached.

HTTP
----
  GET  /health  →  {"status": "ok"}
  POST /api/stt →  Accepts multipart audio file, returns {"text": "<transcribed text>"}
"""

import base64
import json
import logging
from typing import Optional

from fastapi import FastAPI, File, Header, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from brain.fsm import ConversationState, handle_utterance, initial_state
from brain.stt import stt_engine
from brain.tts import tts_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Voice Agent — Clinic Appointment Booking")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Admin API — hardcoded credentials for assessment purposes
# ---------------------------------------------------------------------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_TOKEN = "admin-token-savvpro"


def _require_admin(authorization: Optional[str]):
    """Raise 401 if the bearer token doesn't match."""
    if authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/api/admin/login")
def admin_login(data: dict):
    """Validate admin credentials and return a static bearer token."""
    if (
        data.get("username") == ADMIN_USERNAME
        and data.get("password") == ADMIN_PASSWORD
    ):
        return {"success": True, "token": ADMIN_TOKEN}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/api/admin/appointments")
def admin_get_appointments(authorization: Optional[str] = Header(None)):
    """Return all appointments (booked + cancelled) for the admin dashboard."""
    _require_admin(authorization)
    from brain.availability import APPOINTMENTS

    return {"appointments": list(APPOINTMENTS.values())}


@app.post("/api/admin/appointments/{name_key}/cancel")
def admin_cancel_appointment(
    name_key: str, authorization: Optional[str] = Header(None)
):
    """Allow admin to cancel a specific appointment by patient name key."""
    _require_admin(authorization)
    from brain.availability import cancel_appointment

    result = cancel_appointment(name_key)
    if not result:
        raise HTTPException(status_code=404, detail="Appointment not found or already cancelled")
    return {"success": True, "appointment": result}


@app.post("/api/stt")
async def transcribe_audio_file(file: UploadFile = File(...)):
    """Transcribe an uploaded audio file using local faster-whisper."""
    contents = await file.read()
    suffix = ".wav"
    if file.filename:
        _, ext = file.filename.rsplit(".", 1) if "." in file.filename else ("", "")
        if ext:
            suffix = f".{ext}"
    text = stt_engine.transcribe_bytes(contents, suffix=suffix)
    return {"text": text}


@app.post("/api/tts")
async def synthesize_speech(data: dict):
    """Synthesize speech from text using local Piper TTS."""
    text = data.get("text", "").strip()
    if not text:
        return {"error": "Missing 'text' field", "audio": ""}
    wav_bytes = tts_engine.synthesize_wav_bytes(text)
    audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
    return {
        "text": text,
        "format": "wav",
        "audio": audio_b64,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected")

    # Send opening greeting immediately on connect
    greeting, conv_state = initial_state()
    await _send(websocket, greeting, conv_state)

    try:
        while True:
            # Receive either text or binary message
            message = await websocket.receive()

            user_text = ""
            transcription = ""

            if "bytes" in message and message["bytes"]:
                # Binary audio data received
                audio_bytes = message["bytes"]
                logger.info("Received binary audio frame (%d bytes)", len(audio_bytes))
                transcription = stt_engine.transcribe_bytes(audio_bytes, suffix=".wav")
                user_text = transcription
            elif "text" in message and message["text"]:
                raw = message["text"]
                try:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        if data.get("type") == "audio" and "data" in data:
                            audio_bytes = base64.b64decode(data["data"])
                            fmt = data.get("format", "wav")
                            transcription = stt_engine.transcribe_bytes(audio_bytes, suffix=f".{fmt}")
                            user_text = transcription
                        else:
                            user_text = data.get("text", "").strip()
                    else:
                        user_text = str(raw).strip()
                except (json.JSONDecodeError, AttributeError):
                    user_text = raw.strip()

            if not user_text:
                continue

            logger.info("[%s] User  : %r", conv_state.fsm_state.value, user_text)

            reply, conv_state = handle_utterance(user_text, conv_state)

            logger.info("[%s] Agent : %r", conv_state.fsm_state.value, reply)

            await _send(
                websocket,
                reply,
                conv_state,
                transcription=transcription if transcription else None,
            )

            if conv_state.fsm_state.value == "END":
                await websocket.close()
                break

    except WebSocketDisconnect:
        logger.info("Client disconnected")


async def _send(
    ws: WebSocket,
    reply: str,
    state: ConversationState,
    transcription: Optional[str] = None,
    include_audio: bool = True,
) -> None:
    payload = {
        "reply": reply,
        "state": state.fsm_state.value,
        "slots": state.slots,
    }
    if transcription:
        payload["transcription"] = transcription

    if include_audio and reply:
        try:
            wav_bytes = tts_engine.synthesize_wav_bytes(reply)
            payload["audio"] = base64.b64encode(wav_bytes).decode("ascii")
            payload["audio_format"] = "wav"
        except Exception as exc:
            logger.warning("TTS generation skipped: %s", exc)

    await ws.send_text(json.dumps(payload))


