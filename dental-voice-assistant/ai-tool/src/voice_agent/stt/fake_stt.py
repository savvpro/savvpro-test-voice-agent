"""Fake STT engine for unit testing and offline development."""

from __future__ import annotations

from voice_agent.ports import STTEngine, STTError


class FakeSTT(STTEngine):
    """Fake speech-to-text engine.

    Returns queued strings or decodes raw bytes as UTF-8.
    If a queued item is an Exception, it is raised.
    """

    def __init__(self, queue: list[str | Exception] | None = None) -> None:
        self.queue: list[str | Exception] = list(queue) if queue is not None else []
        self.history: list[bytes] = []

    def queue_text(self, text: str | Exception) -> None:
        """Enqueue next transcription response."""
        self.queue.append(text)

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes."""
        self.history.append(audio_bytes)
        if self.queue:
            item = self.queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        try:
            return audio_bytes.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise STTError("Failed to decode audio bytes as UTF-8 in FakeSTT") from exc
