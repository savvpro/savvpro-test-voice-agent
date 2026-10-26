from datetime import datetime
from zoneinfo import ZoneInfo

from app.booking import BookingStore


def test_capacity_blocks_full_duration() -> None:
    store = BookingStore()
    start = datetime(2026, 10, 27, 10, 0, tzinfo=ZoneInfo("America/Chicago"))
    assert store.confirm({"slot": start.isoformat(), "service": "brake_inspection"}, "ONE")
    assert not store.is_available(start.replace(hour=11), "tire_rotation")


def test_alternatives_rank_deterministically() -> None:
    store = BookingStore()
    requested = datetime(2026, 10, 27, 10, 0, tzinfo=ZoneInfo("America/Chicago"))
    result = store.alternatives(requested, "oil_change")
    assert result[0] == requested
    assert result == sorted(result)
