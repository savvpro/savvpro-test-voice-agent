"""VoicePipeline orchestrating STT -> Brain Agent -> TTS with stage latency timing."""

from __future__ import annotations

import inspect
import logging
import time
from typing import Any

from voice_agent.ports import AudioClip, STTEngine, STTError, TTSEngine, TurnResult

logger = logging.getLogger(__name__)


class VoicePipeline:
    """Voice pipeline connecting speech recognition, deterministic brain, and speech synthesis.

    Attributes
    ----------
    stt: STTEngine
        Speech-to-text transcriber.
    agent: Any
        Turn handler (callable or object with `handle_turn(text, session)`).
    tts: TTSEngine
        Text-to-speech synthesizer.
    """

    def __init__(
        self,
        stt: STTEngine,
        agent: Any,
        tts: TTSEngine,
    ) -> None:
        self.stt = stt
        self.agent = agent
        self.tts = tts

    async def _invoke_agent(self, text: str, session: Any) -> TurnResult:
        """Invoke the brain agent synchronously or asynchronously."""
        if hasattr(self.agent, "handle_turn") and callable(self.agent.handle_turn):
            fn = self.agent.handle_turn
        elif callable(self.agent):
            fn = self.agent
        else:
            raise TypeError("Pipeline agent must be callable or have a handle_turn method")

        if inspect.iscoroutinefunction(fn):
            result = await fn(text, session)
        else:
            result = fn(text, session)

        if not isinstance(result, TurnResult):
            raise TypeError(f"Agent must return TurnResult, got {type(result)}")
        return result

    async def _synthesize(self, text: str) -> AudioClip | None:
        """Synthesize reply text into audio via TTS engine."""
        try:
            res = self.tts.synthesize(text)
            if inspect.isawaitable(res):
                return await res
            return res
        except Exception as exc:
            logger.warning("TTS synthesis threw exception in pipeline: %s", exc)
            return None

    async def handle_audio(
        self,
        session: Any,
        audio_bytes: bytes | None = None,
        mime: str = "audio/wav",
        *,
        bytes: bytes | None = None,
    ) -> TurnResult:
        """Process an incoming audio chunk through STT, Brain, and TTS.

        Accepts audio bytes positionally or via `bytes` keyword argument.
        """
        raw_audio = bytes if bytes is not None else (audio_bytes or b"")
        start_total = time.perf_counter()

        # 1. STT Stage
        t_stt = time.perf_counter()
        stt_failed = False
        user_text = ""
        try:
            res = self.stt.transcribe(raw_audio)
            if inspect.isawaitable(res):
                user_text = await res
            else:
                user_text = res
        except (STTError, Exception) as exc:
            logger.warning("STT transcription failed in pipeline: %s", exc)
            stt_failed = True
            user_text = ""
        stt_ms = (time.perf_counter() - t_stt) * 1000.0

        # If STT failed or returned empty silence, treat as empty utterance (counts as failure in brain)
        if stt_failed and not user_text:
            user_text = ""

        # 2. Brain Stage
        t_brain = time.perf_counter()
        turn_result = await self._invoke_agent(user_text, session)
        brain_ms = (time.perf_counter() - t_brain) * 1000.0

        # 3. TTS Stage
        t_tts = time.perf_counter()
        audio_clip = await self._synthesize(turn_result.reply_text)
        tts_ms = (time.perf_counter() - t_tts) * 1000.0

        total_ms = (time.perf_counter() - start_total) * 1000.0

        turn_result.user_text = user_text
        turn_result.audio = audio_clip.data if audio_clip is not None else None
        turn_result.audio_mime = audio_clip.mime if audio_clip is not None else None
        turn_result.timings = {
            "stt_ms": round(stt_ms, 2),
            "brain_ms": round(brain_ms, 2),
            "tts_ms": round(tts_ms, 2),
            "total_ms": round(total_ms, 2),
        }
        return turn_result

    async def handle_text(self, session: Any, text: str) -> TurnResult:
        """Process direct user text through Brain and TTS with zero STT latency."""
        start_total = time.perf_counter()
        stt_ms = 0.0

        # 1. Brain Stage
        t_brain = time.perf_counter()
        turn_result = await self._invoke_agent(text, session)
        brain_ms = (time.perf_counter() - t_brain) * 1000.0

        # 2. TTS Stage
        t_tts = time.perf_counter()
        audio_clip = await self._synthesize(turn_result.reply_text)
        tts_ms = (time.perf_counter() - t_tts) * 1000.0

        total_ms = (time.perf_counter() - start_total) * 1000.0

        turn_result.user_text = text
        turn_result.audio = audio_clip.data if audio_clip is not None else None
        turn_result.audio_mime = audio_clip.mime if audio_clip is not None else None
        turn_result.timings = {
            "stt_ms": stt_ms,
            "brain_ms": round(brain_ms, 2),
            "tts_ms": round(tts_ms, 2),
            "total_ms": round(total_ms, 2),
        }
        return turn_result
