"""Protocol interfaces (ports) for the voice_agent package.

These are the ONLY points of contact between ai-tool and the outside world.
The brain imports only these protocols; concrete implementations live in
backend/app/services/.
"""

from dataclasses import dataclass, field
from datetime import date, time
from typing import Any, Protocol, runtime_checkable


class STTError(Exception):
    """Raised when speech-to-text transcription fails."""


@dataclass
class AudioClip:
    """Synthesized audio clip with mime type."""

    data: bytes
    mime: str = "audio/mpeg"


@dataclass
class TurnResult:
    """The result returned for one turn."""

    reply_text: str
    state: str
    end_call: bool = False
    action: str | None = None
    slots: dict[str, Any] = field(default_factory=dict)
    audio: bytes | None = None
    audio_mime: str | None = "audio/mpeg"
    user_text: str = ""
    timings: dict[str, float] = field(default_factory=dict)


@runtime_checkable
class STTEngine(Protocol):
    """Speech-to-text engine."""

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Return the transcribed text from *audio_bytes*."""
        ...


@runtime_checkable
class TTSEngine(Protocol):
    """Text-to-speech engine."""

    async def synthesize(self, text: str) -> AudioClip | None:
        """Return audio clip for *text*, or None on failure."""
        ...


class SlotInfo:
    """A bookable time slot."""

    __slots__ = ("date", "start", "end")

    def __init__(self, slot_date: date, start: time, end: time) -> None:
        self.date = slot_date
        self.start = start
        self.end = end

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SlotInfo):
            return NotImplemented
        return (self.date, self.start, self.end) == (other.date, other.start, other.end)

    def __repr__(self) -> str:
        return f"SlotInfo(date={self.date}, start={self.start}, end={self.end})"


@runtime_checkable
class BookingGateway(Protocol):
    """Booking operations exposed to the brain."""

    def free_slots(self, day: date) -> list[SlotInfo]:
        """Return available slots on *day*."""
        ...

    def book(
        self,
        patient_name: str,
        patient_phone: str,
        service: str,
        slot: SlotInfo,
    ) -> str | None:
        """Book a slot.  Returns booking id, or None if the slot is taken."""
        ...

    def cancel(self, booking_id: str) -> bool:
        """Cancel a booking. Returns True on success."""
        ...

    def reschedule(self, booking_id: str, new_slot: SlotInfo) -> str | None:
        """Reschedule atomically. Returns new booking id or None if taken."""
        ...

    def find_upcoming_by_phone(self, phone: str) -> list[tuple[str, SlotInfo]]:
        """Return [(booking_id, slot), ...] for upcoming confirmed appointments."""
        ...


@runtime_checkable
class Clock(Protocol):
    """Injectable clock — never call datetime.now() inside the brain."""

    def today(self) -> date:
        """Return today's date."""
        ...

    def now_time(self) -> time:
        """Return current local time."""
        ...
