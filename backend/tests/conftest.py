from datetime import datetime

import pytest

from app.clinic.calendar import Calendar
from app.dialog.manager import Call

# Monday 26 October 2026, 10:00. Every test runs against this fixed clock.
NOW = datetime(2026, 10, 26, 10, 0)


@pytest.fixture
def now():
    return NOW


@pytest.fixture
def calendar():
    return Calendar(NOW.date())


@pytest.fixture
def call(calendar):
    c = Call(calendar, NOW)
    c.greet()
    return c


def talk(call, *lines):
    """Say each line in turn; return the last Decision."""
    decision = None
    for line in lines:
        decision = call.turn(line)
    return decision
