"""Piper TTS engine (optional offline synthesis)."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

from voice_agent.ports import AudioClip, TTSEngine

logger = logging.getLogger(__name__)


class PiperTTS(TTSEngine):
    """Piper TTS engine implementing TTSEngine with lazy imports."""

    def __init__(self, model_path: str = "", config_path: str = "") -> None:
        self.model_path = model_path
        self.config_path = config_path
        self._voice: Any = None

    def _get_voice(self) -> Any:
        if self._voice is None:
            try:
                from piper.voice import PiperVoice  # type: ignore[import-not-found]

                self._voice = PiperVoice.load(
                    self.model_path,
                    config_path=self.config_path or None,
                )
            except Exception as exc:
                logger.warning("Failed to initialize Piper voice: %s", exc)
                return None
        return self._voice

    def _synthesize_sync(self, text: str) -> AudioClip | None:
        voice = self._get_voice()
        if voice is None:
            return None
        try:
            buf = io.BytesIO()
            voice.synthesize(text, buf)
            return AudioClip(data=buf.getvalue(), mime="audio/wav")
        except Exception as exc:
            logger.warning("Piper synthesis error: %s", exc)
            return None

    async def synthesize(self, text: str) -> AudioClip | None:
        """Synthesize text using Piper offline TTS, returning None on failure."""
        if not text or not text.strip():
            return None
        return await asyncio.to_thread(self._synthesize_sync, text)
