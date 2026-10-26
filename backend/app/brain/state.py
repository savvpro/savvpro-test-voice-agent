from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum

from app.brain.nlu import NLUResult


class State(str, Enum):
    """The question the assistant is currently waiting for an answer to."""

    ASK_SERVICE = "ask_service"
    ASK_WHEN = "ask_when"                      # waiting for a date and/or a time
    OFFER_ALTERNATIVE = "offer_alternative"    # we offered free slots, waiting for a pick
    ASK_PATIENT = "ask_patient"
    ASK_PHONE = "ask_phone"
    CONFIRM = "confirm"
    DONE = "done"


EXPECTING = {
    State.ASK_SERVICE: "service",
    State.ASK_WHEN: "time",
    State.OFFER_ALTERNATIVE: "choice",
    State.ASK_PATIENT: "name",
    State.ASK_PHONE: "phone",
    State.CONFIRM: None,
    State.DONE: None,
}


@dataclass
class Session:
    """Everything the assistant remembers during one call (the 'clipboard')."""

    state: State = State.ASK_SERVICE

    # slots
    service: str | None = None
    appt_date: date | None = None
    appt_time: time | None = None
    name: str | None = None
    phone: str | None = None
    relation: str | None = None          # who the patient is ("mother"), if not the caller

    # conversation memory
    offered_slots: list[datetime] = field(default_factory=list)
    fail_count: int = 0                  # consecutive turns we did not understand
    discount_asks: int = 0               # how many times the caller asked for a discount
    last_reply: str = ""                 # for "say that again"
    booking_ref: str | None = None

    def slots(self) -> dict[str, str | None]:
        """The clipboard as plain strings (used by the API and the UI)."""
        return {
            "service": self.service,
            "date": self.appt_date.isoformat() if self.appt_date else None,
            "time": self.appt_time.strftime("%H:%M") if self.appt_time else None,
            "name": self.name,
            "phone": self.phone,
        }


@dataclass
class TurnResult:
    """What the policy returns for one caller turn."""

    reply: str
    actions: list[str]                   # names of the reply templates that were used
    state: State                         # state AFTER this turn
    nlu: NLUResult | None = None
    trace: list[str] = field(default_factory=list)   # "why" lines for the UI

    @property
    def done(self) -> bool:
        return self.state is State.DONE
