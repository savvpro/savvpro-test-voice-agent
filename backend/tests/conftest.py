"""Shared fixtures: isolate each test run on a temp SQLite file."""

from __future__ import annotations

import pytest

from app.engine import availability
from app.rate_limit import turn_limiter


@pytest.fixture(autouse=True)
def temp_sqlite(tmp_path, monkeypatch):
    db = tmp_path / "test_bookings.db"
    log = tmp_path / "notifications.log"
    monkeypatch.setenv("BOOKINGS_DB", str(db))
    monkeypatch.setenv("NOTIFICATIONS_LOG", str(log))
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    turn_limiter.reset()
    availability.rebind_store(db)
    yield db
    availability.store.reset()
    turn_limiter.reset()
