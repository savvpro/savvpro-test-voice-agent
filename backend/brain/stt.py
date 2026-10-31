"""
Local Speech-to-Text (STT) wrapper using faster-whisper.

Runs fully locally without any external API keys or network calls (after initial model download).
"""

import io
import logging
import os
import tempfile
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Default model size: 'base.en' or 'tiny.en' (low RAM, fast CPU inference)
DEFAULT_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base.en")
DEFAULT_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
DEFAULT_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")


class WhisperSTT:
    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = DEFAULT_DEVICE,
        compute_type: str = DEFAULT_COMPUTE_TYPE,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _load_model(self):
        if self._model is None:
            # Compatibility patch for PyAV 15+ where 'metadata_errors' parameter was removed
            import faster_whisper.audio
            import av

            _orig_av_open = av.open

            def _patched_av_open(*args, **kwargs):
                kwargs.pop("metadata_errors", None)
                return _orig_av_open(*args, **kwargs)

            faster_whisper.audio.av.open = _patched_av_open

            from faster_whisper import WhisperModel
            logger.info(
                "Loading faster-whisper model '%s' on %s (%s)...",
                self.model_size,
                self.device,
                self.compute_type,
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("faster-whisper model loaded successfully.")

    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe an audio file from disk."""
        self._load_model()
        segments, info = self._model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        logger.info("Transcribed (%s, prob=%.2f): %r", info.language, info.language_probability, text)
        return text

    def transcribe_bytes(self, audio_bytes: bytes, suffix: str = ".wav") -> str:
        """Transcribe raw audio bytes by writing to a temporary file."""
        if not audio_bytes:
            return ""

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            return self.transcribe_file(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


# Global singleton instance for easy reuse across endpoints
stt_engine = WhisperSTT()

