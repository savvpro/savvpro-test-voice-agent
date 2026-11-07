"""EdgeTTS engine implementation using Microsoft Edge TTS."""

from __future__ import annotations

import asyncio
import logging

from voice_agent.ports import AudioClip, TTSEngine

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "en-US-JennyNeural"
DEFAULT_TIMEOUT_SECONDS = 8.0


class EdgeTTS(TTSEngine):
    """Text-to-speech engine using edge-tts.

    Collects mp3 bytes and returns AudioClip(data=..., mime="audio/mpeg").
    Enforces an 8-second timeout; returns None on failure or timeout without raising.
    """

    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.voice = voice
        self.timeout = timeout

    async def _synthesize_stream(self, text: str) -> AudioClip | None:
        import edge_tts

        communicate = edge_tts.Communicate(text, self.voice)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])

        if not chunks:
            return None
        return AudioClip(data=b"".join(chunks), mime="audio/mpeg")

    async def synthesize(self, text: str) -> AudioClip | None:
        """Synthesize text into MP3 audio clip with timeout, returning None on failure."""
        if not text or not text.strip():
            return None

        try:
            return await asyncio.wait_for(
                self._synthesize_stream(text),
                timeout=self.timeout,
            )
        except Exception as exc:
            logger.warning("EdgeTTS failed or timed out: %s", exc)
            return None
