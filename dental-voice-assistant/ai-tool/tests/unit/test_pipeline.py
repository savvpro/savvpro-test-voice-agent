"""Unit tests for VoicePipeline including STT and TTS failure paths."""

from typing import Any

import pytest

from voice_agent.brain.responses import FALLBACK
from voice_agent.brain.state import SessionContext, State
from voice_agent.pipeline import VoicePipeline
from voice_agent.ports import STTError, TurnResult
from voice_agent.stt.fake_stt import FakeSTT
from voice_agent.tts.fake_tts import FakeTTS


class DummyAgent:
    """Mock agent tracking turns and returning deterministic TurnResult."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def handle_turn(self, text: str, ctx: SessionContext) -> TurnResult:
        self.calls.append((text, ctx))
        if not text.strip():
            ctx.fail_count += 1
            return TurnResult(reply_text=FALLBACK, state=ctx.state.value)
        return TurnResult(reply_text="How can I help you?", state=ctx.state.value)


@pytest.mark.asyncio
async def test_pipeline_handle_text_success() -> None:
    stt = FakeSTT()
    tts = FakeTTS()
    agent = DummyAgent()
    pipeline = VoicePipeline(stt=stt, agent=agent, tts=tts)

    ctx = SessionContext(state=State.START)
    res = await pipeline.handle_text(ctx, "hello")

    assert res.user_text == "hello"
    assert res.reply_text == "How can I help you?"
    assert res.audio is not None
    assert res.audio_mime == "audio/mpeg"
    assert "brain_ms" in res.timings
    assert "tts_ms" in res.timings
    assert res.timings["stt_ms"] == 0.0


@pytest.mark.asyncio
async def test_pipeline_handle_audio_success() -> None:
    stt = FakeSTT()
    tts = FakeTTS()
    agent = DummyAgent()
    pipeline = VoicePipeline(stt=stt, agent=agent, tts=tts)

    ctx = SessionContext(state=State.START)
    audio_data = b"book cleaning"
    res = await pipeline.handle_audio(ctx, audio_bytes=audio_data)

    assert res.user_text == "book cleaning"
    assert res.reply_text == "How can I help you?"
    assert res.audio is not None
    assert res.timings["stt_ms"] >= 0.0


@pytest.mark.asyncio
async def test_pipeline_handle_audio_bytes_kwarg() -> None:
    stt = FakeSTT()
    tts = FakeTTS()
    agent = DummyAgent()
    pipeline = VoicePipeline(stt=stt, agent=agent, tts=tts)

    ctx = SessionContext(state=State.START)
    res = await pipeline.handle_audio(ctx, bytes=b"reschedule")

    assert res.user_text == "reschedule"


@pytest.mark.asyncio
async def test_pipeline_stt_failure_reprompt() -> None:
    stt = FakeSTT()
    stt.queue_text(STTError("Transcription device failure"))
    tts = FakeTTS()
    agent = DummyAgent()
    pipeline = VoicePipeline(stt=stt, agent=agent, tts=tts)

    ctx = SessionContext(state=State.START)
    res = await pipeline.handle_audio(ctx, b"noisy audio")

    # STT failed -> empty text sent to agent -> friendly reprompt
    assert res.user_text == ""
    assert res.reply_text == FALLBACK
    assert ctx.fail_count == 1
    assert res.audio is not None


@pytest.mark.asyncio
async def test_pipeline_tts_failure_returns_none_audio() -> None:
    stt = FakeSTT()
    tts = FakeTTS(should_fail=True)
    agent = DummyAgent()
    pipeline = VoicePipeline(stt=stt, agent=agent, tts=tts)

    ctx = SessionContext(state=State.START)
    res = await pipeline.handle_text(ctx, "cancel appointment")

    assert res.reply_text == "How can I help you?"
    assert res.audio is None


@pytest.mark.asyncio
async def test_pipeline_callable_agent() -> None:
    stt = FakeSTT()
    tts = FakeTTS()

    def functional_agent(text: str, session: SessionContext) -> TurnResult:
        return TurnResult(reply_text="Function response", state="START")

    pipeline = VoicePipeline(stt=stt, agent=functional_agent, tts=tts)
    ctx = SessionContext(state=State.START)
    res = await pipeline.handle_text(ctx, "hi")

    assert res.reply_text == "Function response"
