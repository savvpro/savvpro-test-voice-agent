"""Plain data structures shared by the brain, services and API layers."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum


class Intent(str, Enum):
    BOOK = "book"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"


class State(str, Enum):
    ASK_INTENT = "ask_intent"  # waiting to learn what the caller wants
    COLLECTING = "collecting"  # filling slots (doctor, day, time, name, phone)
    OFFERING = "offering"  # slot unavailable / vague: caller picks from options
    CONFIRMING = "confirming"  # read-back, waiting for yes / no
    ASK_MORE = "ask_more"  # job done, "anything else?"
    ENDED = "ended"
    HANDOFF = "handoff"  # transferred to a human


@dataclass(frozen=True)
class Doctor:
    key: str
    name: str
    label: str


DOCTORS: dict[str, Doctor] = {
    "general": Doctor("general", "Dr. Khan", "general"),
    "dental": Doctor("dental", "Dr. Ahmed", "dental"),
    "skin": Doctor("skin", "Dr. Raza", "skin"),
}


@dataclass
class Appointment:
    id: int
    name: str
    phone: str
    specialty: str
    start: dt.datetime


@dataclass
class Slots:
    specialty: str | None = None
    day: dt.date | None = None
    at: dt.time | None = None
    name: str | None = None
    phone: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "specialty": self.specialty,
            "day": self.day.isoformat() if self.day else None,
            "at": self.at.strftime("%H:%M") if self.at else None,
            "name": self.name,
            "phone": self.phone,
        }


@dataclass
class Trace:
    """Everything the UI needs to show *why* the brain did what it did."""

    heard: str
    state_before: str
    state_after: str = ""
    intents: list[str] = field(default_factory=list)
    entities: dict[str, str] = field(default_factory=dict)
    rule: str = ""
    notes: list[str] = field(default_factory=list)

    def note(self, message: str) -> None:
        self.notes.append(message)


@dataclass
class Session:
    id: str
    state: State = State.ASK_INTENT
    intent: Intent | None = None
    slots: Slots = field(default_factory=Slots)
    pending: str | None = None  # the question currently awaiting an answer
    last_prompt: str = ""
    last_example: str = ""
    last_reply: str = ""
    daypart: str | None = None
    vague_date: bool = False
    offers: list[dt.datetime] = field(default_factory=list)
    existing: Appointment | None = None
    notice: str | None = None
    phone_problem: bool = False
    phone_partial: str = ""  # digits heard so far when a number arrives in pieces
    lookup_attempts: int = 0
    fails: int = 0
    turns: int = 0

    def reset_flow(self, keep_contact: bool = True) -> None:
        name, phone = self.slots.name, self.slots.phone
        self.slots = Slots(name=name if keep_contact else None, phone=phone if keep_contact else None)
        self.intent = None
        self.daypart = None
        self.vague_date = False
        self.offers = []
        self.existing = None
        self.notice = None
        self.phone_problem = False
        self.phone_partial = ""
        self.lookup_attempts = 0


@dataclass
class TurnResult:
    reply: str
    trace: Trace
    session: Session

    @property
    def ended(self) -> bool:
        return self.session.state in (State.ENDED, State.HANDOFF)
