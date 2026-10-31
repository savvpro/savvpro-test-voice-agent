"""
Tests for local faster-whisper STT integration.
"""

import io
import wave
import pytest
from brain.stt import WhisperSTT, stt_engine


def create_dummy_wav_bytes(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Create a short silent WAV file in memory to test audio pipeline mechanics."""
    buf = io.BytesIO()
    num_frames = int(duration_sec * sample_rate)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # write 0s (silence)
        wf.writeframes(b"\x00\x00" * num_frames)
    return buf.getvalue()


class TestSTTEngine:
    def test_stt_initialization(self):
        engine = WhisperSTT(model_size="base.en", device="cpu")
        assert engine.model_size == "base.en"
        assert engine.device == "cpu"
        assert engine._model is None

    def test_transcribe_empty_bytes(self):
        result = stt_engine.transcribe_bytes(b"")
        assert result == ""

    def test_transcribe_dummy_silent_wav(self):
        silent_wav = create_dummy_wav_bytes(duration_sec=0.5)
        # Should transcribe cleanly (silent audio produces empty or near empty string)
        result = stt_engine.transcribe_bytes(silent_wav)
        assert isinstance(result, str)

