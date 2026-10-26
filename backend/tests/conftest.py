"""Shared pytest fixtures for the REDELIVER test suite.

Provides:
- ``client``: a ``TestClient`` wired to the FastAPI app.
- ``frozen_clock``: a deterministic ``datetime`` used everywhere instead of
  the system clock.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_clock, get_parcel_repo, get_session_store
from app.core.config import Settings, get_settings
from app.data.loader import load_parcels, load_pickup_points, load_slots
from app.data.repository import InMemoryParcelRepository, InMemorySessionStore
from app.main import create_app

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _test_settings() -> Settings:
    """Return settings tuned for tests (e.g. relaxed CORS)."""
    return Settings(
        cors_origins="*",
        log_level="WARNING",
        app_env="test",
    )


@pytest.fixture()
def client(frozen_clock: datetime) -> TestClient:
    """Fresh ``TestClient`` per test with overridden settings."""
    app = create_app()
    app.dependency_overrides[get_settings] = _test_settings
    app.dependency_overrides[get_clock] = lambda: frozen_clock
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def frozen_clock() -> datetime:
    """A fixed point in time used by all date/time-sensitive tests.

    Monday 2026-10-26 14:30 Pakistan Standard Time.
    """
    return datetime(
        2026, 10, 26, 14, 30,
        tzinfo=timezone(timedelta(hours=5), name="PKT"),
    )


@pytest.fixture()
def api_services(client: TestClient, frozen_clock: datetime):
    repo = InMemoryParcelRepository(
        load_parcels(DATA_DIR),
        load_slots(DATA_DIR, frozen_clock),
        load_pickup_points(DATA_DIR),
    )
    store = InMemorySessionStore()
    client.app.dependency_overrides[get_parcel_repo] = lambda: repo
    client.app.dependency_overrides[get_session_store] = lambda: store
    return client, repo, store
