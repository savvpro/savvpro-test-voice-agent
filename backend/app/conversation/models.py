from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    ABORTED = "aborted"
    EXPIRED = "expired"
    ENDED = "ended"


class State(StrEnum):
    COLLECTING = "collecting"
    CHOOSING_SLOT = "choosing_slot"
    CONFIRMING = "confirming"


@dataclass(frozen=True)
class ServiceSpec:
    key: str
    label: str
    duration_minutes: int
    resource: str


@dataclass
class Session:
    conversation_id: str
    now: datetime
    status: Status = Status.ACTIVE
    state: State | None = State.COLLECTING
    version: int = 0
    last_activity_at: datetime | None = None
    last_question: str = "name"
    expected_answer: str = "text"
    draft: dict[str, Any] = field(default_factory=dict)
    retries: dict[str, int] = field(default_factory=dict)
    recognition_failures: int = 0
    offered_slots: list[str] = field(default_factory=list)
    processed_turns: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.last_activity_at is None:
            self.last_activity_at = self.now
