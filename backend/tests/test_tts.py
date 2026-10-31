"""
Tests for local Piper TTS integration.
"""

import io
import wave
import pytest
from brain.tts import PiperTTS, tts_engine


class TestTTSEngine:
    def test_tts_initialization(self):
        engine = PiperTTS()
        assert "lessac" in engine.model_path.lower()
        assert engine._voice is None

    def test_synthesize_empty_string(self):
        audio_bytes = tts_engine.synthesize_wav_bytes("")
        assert audio_bytes == b""

    def test_synthesize_valid_speech(self):
        text = "Hello! Your appointment has been booked."
        audio_bytes = tts_engine.synthesize_wav_bytes(text)

        assert len(audio_bytes) > 1000
        # Validate that it is a valid RIFF WAV audio format
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2  # 16-bit PCM
            assert wf.getframerate() == 22050
            assert wf.getnframes() > 0
