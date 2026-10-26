from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from app.booking import BookingStore
from app.conversation.engine import ConversationEngine
from app.main import app, sessions, store
from fastapi.testclient import TestClient

FIXED_NOW = datetime(2026, 10, 26, 9, 0, tzinfo=ZoneInfo("America/Chicago"))


@pytest.fixture
def engine() -> ConversationEngine:
    return ConversationEngine(BookingStore(), clock=lambda: FIXED_NOW)


@pytest.fixture
def client() -> TestClient:
    sessions.clear()
    store.bookings.clear()
    return TestClient(app)
