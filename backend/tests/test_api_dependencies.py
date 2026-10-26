"""Default dependency providers initialize their cached runtime services."""

from __future__ import annotations

from datetime import timedelta

from app.api.dependencies import (
    clear_service_caches,
    get_clock,
    get_parcel_repo,
    get_runtime_settings,
    get_session_store,
)
from app.core.config import get_settings


def test_default_service_dependencies_load_and_cache():
    clear_service_caches()
    try:
        store = get_session_store()
        assert get_session_store() is store

        repo = get_parcel_repo()
        assert get_parcel_repo() is repo
        assert repo.get_parcel("RD30000001") is not None
        assert len(repo.list_pickup_points()) == 5

        clock = get_clock()
        assert clock.utcoffset() == timedelta(hours=5)
        assert clock.tzname() == "PKT"
        assert get_runtime_settings(get_settings()) is get_settings()
    finally:
        clear_service_caches()
