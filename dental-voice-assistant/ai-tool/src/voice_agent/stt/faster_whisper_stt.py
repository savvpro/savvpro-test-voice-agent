"""FasterWhisperSTT implementation using faster-whisper."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

from voice_agent.ports import STTEngine, STTError

logger = logging.getLogger(__name__)

CLINIC_VOCABULARY_PROMPT = (
    "BrightSmile Dental Clinic, checkup, cleaning, filling, whitening, "
    "root canal, braces consultation, appointment, reschedule, cancel, Dr., dentist."
)

SILENCE_HALLUCINATIONS: set[str] = {
    "thank you",
    "thank you.",
    "you",
    "you.",
    "thanks for watching",
    "thanks for watching.",
    "thank you for watching.",
    "subscribe",
    "subtitles by",
}


class FasterWhisperSTT(STTEngine):
    """FasterWhisper speech-to-text engine.

    Loads WhisperModel once upon initialization and performs non-blocking
    transcription offloaded to a thread pool via asyncio.to_thread.
    """

    def __init__(
        self,
        model_size_or_path: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        initial_prompt: str = CLINIC_VOCABULARY_PROMPT,
        **model_kwargs: Any,
    ) -> None:
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "faster-whisper is not installed. Install via `pip install faster-whisper`."
            ) from exc

        self.model = WhisperModel(
            model_size_or_path,
            device=device,
            compute_type=compute_type,
            **model_kwargs,
        )
        self.initial_prompt = initial_prompt

    def _transcribe_sync(self, audio_bytes: bytes) -> str:
        """Synchronous transcription executed in a worker thread."""
        buffer = io.BytesIO(audio_bytes)
        try:
            segments, _info = self.model.transcribe(
                buffer,
                vad_filter=True,
                language="en",
                beam_size=1,
                initial_prompt=self.initial_prompt,
            )
            raw_text = " ".join(seg.text for seg in segments).strip()
        except Exception as exc:
            raise STTError(f"Whisper transcription failed: {exc}") from exc

        # Check silence hallucinations
        normalized = raw_text.strip().lower()
        if not normalized or normalized in SILENCE_HALLUCINATIONS:
            return ""

        return raw_text

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe raw audio bytes to text asynchronously."""
        if not audio_bytes:
            return ""
        try:
            return await asyncio.to_thread(self._transcribe_sync, audio_bytes)
        except STTError:
            raise
        except Exception as exc:
            raise STTError(f"Unexpected error during transcription: {exc}") from exc
