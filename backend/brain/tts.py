"""
Local Text-to-Speech (TTS) wrapper using Piper.

Runs fully locally without any external API keys or cloud dependencies.
Synthesizes speech into standard PCM 16-bit WAV audio bytes.
"""

import io
import logging
import os
import wave
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = os.getenv(
    "PIPER_MODEL_PATH",
    str(Path(__file__).resolve().parent.parent / "models" / "en_US-lessac-medium.onnx"),
)
DEFAULT_CONFIG_PATH = os.getenv(
    "PIPER_CONFIG_PATH",
    str(Path(__file__).resolve().parent.parent / "models" / "en_US-lessac-medium.onnx.json"),
)


class PiperTTS:
    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        config_path: Optional[str] = DEFAULT_CONFIG_PATH,
        use_cuda: bool = False,
    ):
        self.model_path = model_path
        self.config_path = config_path
        self.use_cuda = use_cuda
        self._voice = None

    def _load_voice(self):
        if self._voice is None:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(
                    f"Piper voice model not found at '{self.model_path}'."
                )
            import piper
            logger.info("Loading Piper voice model from '%s'...", self.model_path)
            self._voice = piper.PiperVoice.load(
                self.model_path,
                config_path=self.config_path,
                use_cuda=self.use_cuda,
            )
            logger.info("Piper voice model loaded successfully.")

    def synthesize_wav_bytes(self, text: str) -> bytes:
        """
        Synthesize speech from *text* and return complete WAV audio bytes.
        """
        clean_text = text.strip()
        if not clean_text:
            return b""

        self._load_voice()

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            self._voice.synthesize_wav(clean_text, wav_file)

        wav_bytes = buf.getvalue()
        logger.info("Synthesized %d bytes of audio for text: %r", len(wav_bytes), clean_text[:40])
        return wav_bytes


# Global singleton instance for easy reuse across endpoints
tts_engine = PiperTTS()
