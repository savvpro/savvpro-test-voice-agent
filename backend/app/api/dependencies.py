"""Shared API dependencies and lazily initialized in-memory services."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.data.loader import load_parcels, load_pickup_points, load_slots
from app.data.repository import InMemoryParcelRepository, InMemorySessionStore

PAKISTAN_TIME = timezone(timedelta(hours=5), name="PKT")


@lru_cache(maxsize=1)
def _session_store() -> InMemorySessionStore:
    return InMemorySessionStore()


@lru_cache(maxsize=1)
def _parcel_repository() -> InMemoryParcelRepository:
    settings = get_settings()
    data_dir = Path(settings.data_dir)
    if not data_dir.is_absolute():
        data_dir = Path(__file__).resolve().parents[2] / data_dir
    clock = get_clock()
    return InMemoryParcelRepository(
        parcels=load_parcels(data_dir),
        slots=load_slots(data_dir, clock),
        pickup_points=load_pickup_points(data_dir),
        max_phone_attempts=settings.max_phone_attempts,
    )


def get_session_store() -> InMemorySessionStore:
    return _session_store()


def get_parcel_repo() -> InMemoryParcelRepository:
    return _parcel_repository()


def get_runtime_settings(settings: Annotated[Settings, Depends(get_settings)]) -> Settings:
    return settings


def get_clock() -> datetime:
    """Return the current Pakistan local time; tests override this dependency."""
    return datetime.fromtimestamp(time.time(), tz=PAKISTAN_TIME)


def clear_service_caches() -> None:
    """Clear process singletons; intended for app lifecycle and tests."""
    _session_store.cache_clear()
    _parcel_repository.cache_clear()
