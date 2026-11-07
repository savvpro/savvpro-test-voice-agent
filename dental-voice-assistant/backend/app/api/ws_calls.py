"""WebSocket endpoint /ws/calls for live voice assistant sessions."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from voice_agent.brain import handle_turn, responses
from voice_agent.brain.state import SessionContext, State
from voice_agent.pipeline import VoicePipeline
from voice_agent.ports import STTEngine, TTSEngine, TurnResult

from app.config import settings
from app.db.engine import async_session_factory
from app.schemas import CallEndedMessage, ErrorMessage, TurnMessage
from app.services.booking_gateway import ClinicRules, SqlBookingGateway
from app.services.clock import SystemClock

logger = logging.getLogger(__name__)

router = APIRouter(tags=["calls"])


@router.websocket("/ws/calls")
async def websocket_calls(websocket: WebSocket) -> None:
    """Live bidirectional audio/text voice assistant WebSocket connection."""
    app = websocket.app
    active_calls = getattr(app.state, "active_calls", 0)

    # 1. Check MAX_CONCURRENT_CALLS
    if active_calls >= settings.max_concurrent_calls:
        await websocket.accept()
        busy_msg = ErrorMessage(
            error="busy",
            detail="Maximum concurrent calls reached. Please try again shortly.",
        )
        await websocket.send_json(busy_msg.model_dump())
        await websocket.close(code=1008, reason="busy")
        return

    await websocket.accept()
    app.state.active_calls = active_calls + 1

    session_id = str(uuid.uuid4())
    session_store = getattr(app.state, "session_store", None)
    ctx = SessionContext(state=State.START)

    if session_store:
        session_store.set(session_id, ctx.to_dict())

    stt: STTEngine = app.state.stt
    tts: TTSEngine = app.state.tts
    clock = getattr(app.state, "clock", SystemClock())

    gateway = getattr(app.state, "gateway", None)
    if gateway is None:
        gateway = SqlBookingGateway(
            session_factory=async_session_factory,
            rules=ClinicRules(),
        )

    def agent_handler(text: str, session: SessionContext) -> TurnResult:
        return handle_turn(text, session, gateway, clock)

    pipeline = VoicePipeline(stt=stt, agent=agent_handler, tts=tts)

    # 2. Send greeting turn 0 with synthesized TTS audio
    t0 = time.perf_counter()
    greeting_audio = await tts.synthesize(responses.GREETING)
    tts_ms = (time.perf_counter() - t0) * 1000.0

    b64_audio = (
        base64.b64encode(greeting_audio.data).decode("ascii")
        if greeting_audio is not None
        else None
    )

    turn_0 = TurnMessage(
        turn=0,
        user_text="",
        reply_text=responses.GREETING,
        state=State.START.value,
        end_call=False,
        audio=b64_audio,
        audio_mime=greeting_audio.mime if greeting_audio else "audio/mpeg",
        timings={
            "stt_ms": 0.0,
            "brain_ms": 0.0,
            "tts_ms": round(tts_ms, 2),
            "total_ms": round(tts_ms, 2),
        },
    )
    await websocket.send_json(turn_0.model_dump())

    turn_index = 0
    message_timestamps: list[float] = []

    try:
        while True:
            # Enforce idle timeout
            try:
                raw_frame = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=settings.call_idle_timeout_seconds,
                )
            except TimeoutError:
                logger.info(
                    "Call timed out due to caller inactivity",
                    extra={"session_id": session_id},
                )
                await websocket.send_json(CallEndedMessage(reason="idle_timeout").model_dump())
                await websocket.close(code=1000, reason="idle_timeout")
                break

            if raw_frame.get("type") == "websocket.disconnect":
                break

            # Rate limit check (sliding window 1s)
            now = time.monotonic()
            message_timestamps = [ts for ts in message_timestamps if now - ts < 1.0]
            if len(message_timestamps) >= int(settings.rate_limit_messages_per_second):
                await websocket.send_json(
                    ErrorMessage(
                        error="rate_limit_exceeded",
                        detail="Rate limit exceeded. Please slow down.",
                    ).model_dump()
                )
                continue
            message_timestamps.append(now)

            # Turn cap enforcement
            if turn_index >= settings.max_turns:
                turn_msg = TurnMessage(
                    turn=turn_index + 1,
                    user_text="",
                    reply_text=responses.MAX_TURNS_END,
                    state=State.END.value,
                    end_call=True,
                )
                await websocket.send_json(turn_msg.model_dump())
                await websocket.send_json(CallEndedMessage(reason="max_turns").model_dump())
                await websocket.close(code=1000, reason="max_turns")
                break

            # Handle Binary Frame (Audio)
            if "bytes" in raw_frame and raw_frame["bytes"] is not None:
                audio_bytes: bytes = raw_frame["bytes"]
                if len(audio_bytes) > settings.max_audio_bytes:
                    err_msg = (
                        f"Audio payload ({len(audio_bytes)} bytes) exceeds max "
                        f"limit of {settings.max_audio_bytes} bytes."
                    )
                    await websocket.send_json(
                        ErrorMessage(error="oversize_audio", detail=err_msg).model_dump()
                    )
                    continue

                turn_result = await pipeline.handle_audio(ctx, audio_bytes=audio_bytes)
                turn_index += 1

                audio_str = (
                    base64.b64encode(turn_result.audio).decode("ascii")
                    if turn_result.audio
                    else None
                )
                turn_msg = TurnMessage(
                    turn=turn_index,
                    user_text=turn_result.user_text,
                    reply_text=turn_result.reply_text,
                    state=turn_result.state,
                    end_call=turn_result.end_call,
                    action=turn_result.action,
                    slots=turn_result.slots,
                    audio=audio_str,
                    audio_mime=turn_result.audio_mime,
                    timings=turn_result.timings,
                )
                await websocket.send_json(turn_msg.model_dump())

                if session_store:
                    session_store.set(session_id, ctx.to_dict())

                if turn_result.end_call:
                    await websocket.send_json(CallEndedMessage(reason="completed").model_dump())
                    await websocket.close(code=1000, reason="completed")
                    break

            # Handle Text Frame (JSON)
            elif "text" in raw_frame and raw_frame["text"] is not None:
                text_frame: str = raw_frame["text"]
                try:
                    payload = json.loads(text_frame)
                    if not isinstance(payload, dict):
                        raise ValueError("Payload must be a JSON object")
                except Exception:
                    await websocket.send_json(
                        ErrorMessage(
                            error="bad_json",
                            detail="Message frame must be a valid JSON object.",
                        ).model_dump()
                    )
                    continue

                msg_type = payload.get("type")
                if msg_type == "end":
                    await websocket.send_json(CallEndedMessage(reason="user_hangup").model_dump())
                    await websocket.close(code=1000, reason="user_hangup")
                    break

                if msg_type == "user_text":
                    input_text = payload.get("text", "")
                    if not isinstance(input_text, str):
                        await websocket.send_json(
                            ErrorMessage(
                                error="bad_json", detail="'text' field must be a string."
                            ).model_dump()
                        )
                        continue

                    if len(input_text) > settings.max_text_chars:
                        err_text = f"Text length exceeds {settings.max_text_chars} chars limit."
                        await websocket.send_json(
                            ErrorMessage(error="oversize_text", detail=err_text).model_dump()
                        )
                        continue

                    turn_result = await pipeline.handle_text(ctx, text=input_text)
                    turn_index += 1

                    audio_str = (
                        base64.b64encode(turn_result.audio).decode("ascii")
                        if turn_result.audio
                        else None
                    )
                    turn_msg = TurnMessage(
                        turn=turn_index,
                        user_text=turn_result.user_text,
                        reply_text=turn_result.reply_text,
                        state=turn_result.state,
                        end_call=turn_result.end_call,
                        action=turn_result.action,
                        slots=turn_result.slots,
                        audio=audio_str,
                        audio_mime=turn_result.audio_mime,
                        timings=turn_result.timings,
                    )
                    await websocket.send_json(turn_msg.model_dump())

                    if session_store:
                        session_store.set(session_id, ctx.to_dict())

                    if turn_result.end_call:
                        await websocket.send_json(CallEndedMessage(reason="completed").model_dump())
                        await websocket.close(code=1000, reason="completed")
                        break
                else:
                    detail_err = (
                        f"Unknown message type '{msg_type}'. Expected 'user_text' or 'end'."
                    )
                    await websocket.send_json(
                        ErrorMessage(error="bad_json", detail=detail_err).model_dump()
                    )
                    continue

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client", extra={"session_id": session_id})
    except Exception as exc:
        logger.exception("Error in websocket session %s: %s", session_id, exc)
    finally:
        app.state.active_calls = max(0, getattr(app.state, "active_calls", 1) - 1)
        if session_store:
            session_store.delete(session_id)
