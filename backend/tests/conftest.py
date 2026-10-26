from datetime import datetime

import pytest

from app.brain.assistant import Assistant
from app.services.booking import ClinicCalendar

NOW = datetime(2026, 10, 26, 10, 0)  # Monday 10:00


@pytest.fixture
def calendar():
    return ClinicCalendar()


@pytest.fixture
def call(calendar):
    """A started call with a frozen clock. Use: bot = call; bot.hear('...')."""
    bot = Assistant(calendar, clock=lambda: NOW)
    bot.start()
    return bot
