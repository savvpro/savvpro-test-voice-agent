"""Shared fixtures: a deterministic clock and a small helper for scripted phone calls."""

from __future__ import annotations

import datetime as dt

import pytest

from app.brain.models import Session
from app.brain.policy import DialogueManager
from app.services.scheduler import Scheduler

MONDAY_8AM = dt.datetime(2026, 11, 2, 8, 0)  # fixed "now" so tests never depend on the real date
TOMORROW = dt.date(2026, 11, 3)  # Tuesday
FRIDAY = dt.date(2026, 11, 6)
SUNDAY = dt.date(2026, 11, 8)
GOOD_PHONE = "zero three two one one two three four five six seven"
GOOD_PHONE_DIGITS = "03211234567"


class Call:
    def __init__(self, now: dt.datetime = MONDAY_8AM):
        self.now = now
        self.scheduler = Scheduler(lambda: self.now)
        self.manager = DialogueManager(self.scheduler, lambda: self.now)
        self.session = Session(id="test")
        self.greeting = self.manager.start(self.session).reply
        self.last = None

    def say(self, text: str, confidence: float | None = None) -> str:
        self.last = self.manager.handle(self.session, text, confidence)
        return self.last.reply

    @property
    def state(self) -> str:
        return self.session.state.value

    @property
    def rule(self) -> str:
        return self.last.trace.rule

    # --- slot finders (the fake schedule is deterministic but pseudo-random) ---
    def free_slots(self, specialty: str, day: dt.date) -> list[dt.datetime]:
        return self.scheduler.free_slots(specialty, day)

    def busy_slot(self, specialty: str, day: dt.date) -> dt.datetime:
        return next(s for s in self.scheduler.slot_times(day) if self.scheduler._seeded_busy(specialty, s))


@pytest.fixture
def call() -> Call:
    return Call()


@pytest.fixture
def make_call():
    return Call
