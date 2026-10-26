"""Text-to-speech behind a small interface, so the provider can be swapped or faked."""

import io
import logging
import wave
from pathlib import Path
from typing import Protocol

from app.config import Settings

logger = logging.getLogger(__name__)


class TextToSpeech(Protocol):
    mime: str

    def synthesize(self, text: str) -> bytes | None: ...


class NullTTS:
    """No server-side voice: the frontend speaks the reply with the browser's speechSynthesis."""

    mime = "audio/wav"

    def synthesize(self, text: str) -> bytes | None:
        return None


class PiperTTS:
    """Local Piper voice (ONNX). Returns a complete WAV file."""

    mime = "audio/wav"

    def __init__(self, voice_path: Path):
        from piper import PiperVoice

        if not voice_path.exists():
            raise FileNotFoundError(voice_path)
        self.voice = PiperVoice.load(voice_path, config_path=f"{voice_path}.json")

    def synthesize(self, text: str) -> bytes | None:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            self.voice.synthesize_wav(text, wav)
        return buffer.getvalue()


def build_tts(settings: Settings) -> TextToSpeech:
    """The configured voice, or NullTTS if it is disabled or fails to load."""
    provider = settings.tts_provider.lower()
    if provider == "none":
        logger.info("text-to-speech disabled (TTS_PROVIDER=none): the browser will speak")
        return NullTTS()
    if provider != "piper":
        logger.warning("unknown TTS_PROVIDER %r: the browser will speak", settings.tts_provider)
        return NullTTS()
    try:
        tts = PiperTTS(settings.piper_voice_path)
    except Exception as exc:
        logger.warning(
            "could not load piper voice %s (%r); the browser will speak. "
            "Run `python scripts/download_models.py`.",
            settings.piper_voice_path,
            exc,
        )
        return NullTTS()
    logger.info("text-to-speech: piper %s", settings.tts_voice)
    return tts
