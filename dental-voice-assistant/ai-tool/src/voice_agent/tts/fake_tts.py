"""Fake TTS engine for testing."""

from __future__ import annotations

from voice_agent.ports import AudioClip, TTSEngine


class FakeTTS(TTSEngine):
    """Fake text-to-speech engine returning deterministic AudioClip."""

    def __init__(
        self, should_fail: bool = False, fixed_bytes: bytes = b"ID3\x03\x00\x00\x00FAKE_AUDIO"
    ) -> None:
        self.history: list[str] = []
        self.should_fail = should_fail
        self.fixed_bytes = fixed_bytes

    async def synthesize(self, text: str) -> AudioClip | None:
        """Synthesize text into a deterministic fake AudioClip or return None if failing."""
        self.history.append(text)
        if self.should_fail:
            return None
        return AudioClip(data=self.fixed_bytes, mime="audio/mpeg")
