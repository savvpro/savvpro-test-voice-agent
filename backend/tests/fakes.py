"""Stand-ins for the speech engines, so API tests don't load any model."""

from app.speech.stt import Transcription

FAKE_WAV = b"RIFF\x24\x00\x00\x00WAVEfmt "


class FakeSTT:
    """'Transcribes' audio that is really UTF-8 text."""

    def __init__(self):
        self.calls = 0

    def transcribe(self, audio: bytes) -> Transcription:
        self.calls += 1
        return Transcription(text=audio.decode("utf-8"), confidence=0.9)


class BrokenSTT:
    def transcribe(self, audio: bytes) -> Transcription:
        raise ValueError("Invalid data found when processing input")


class FakeTTS:
    mime = "audio/wav"

    def __init__(self):
        self.spoken: list[str] = []

    def synthesize(self, text: str) -> bytes | None:
        self.spoken.append(text)
        return FAKE_WAV


class BrokenTTS:
    mime = "audio/wav"

    def synthesize(self, text: str) -> bytes | None:
        raise RuntimeError("onnx session crashed")
