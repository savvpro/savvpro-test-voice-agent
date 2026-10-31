"""
FastAPI WebSocket server for the Voice Agent (text-only, no audio).

WebSocket: ws://localhost:8000/ws

Protocol
--------
  Client → Server  :  {"text": "<caller utterance>"}
  Server → Client  :  {"reply": "<agent reply>",
                        "state": "<FSM state name>",
                        "slots": {<filled slots>}}

  On connect the server immediately sends the opening greeting.
  The connection is closed by the server when FSMState.END is reached.

HTTP
----
  GET /health  →  {"status": "ok"}
"""

import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from brain.fsm import ConversationState, handle_utterance, initial_state

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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected")

    # Send opening greeting immediately on connect
    greeting, conv_state = initial_state()
    await _send(websocket, greeting, conv_state)

    try:
        while True:
            raw = await websocket.receive_text()

            # Accept either plain text or {"text": "..."}
            try:
                data      = json.loads(raw)
                user_text = data.get("text", "").strip()
            except (json.JSONDecodeError, AttributeError):
                user_text = raw.strip()

            if not user_text:
                continue

            logger.info("[%s] User  : %r", conv_state.fsm_state.value, user_text)

            reply, conv_state = handle_utterance(user_text, conv_state)

            logger.info("[%s] Agent : %r", conv_state.fsm_state.value, reply)

            await _send(websocket, reply, conv_state)

            if conv_state.fsm_state.value == "END":
                await websocket.close()
                break

    except WebSocketDisconnect:
        logger.info("Client disconnected")


async def _send(ws: WebSocket, reply: str, state: ConversationState) -> None:
    await ws.send_text(json.dumps({
        "reply": reply,
        "state": state.fsm_state.value,
        "slots": state.slots,
    }))

