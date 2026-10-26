"""Tests for the service layer (verification, booking, pickup, cancellation).

Uses the real InMemoryParcelRepository with frozen_clock fixtures for
deterministic testing.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.data.loader import load_parcels, load_pickup_points, load_slots
from app.data.repository import InMemoryParcelRepository
from app.services.booking import (
    book_slot,
    find_nearest_available,
    get_available_slots,
    rebook_slot,
    release_slot,
)
from app.services.cancellation import cancel_parcel
from app.services.pickup import get_pickup_point, list_pickup_points
from app.services.verification import verify_phone, verify_tracking_id

CLOCK = datetime(2026, 10, 26, 14, 30, tzinfo=timezone(timedelta(hours=5), name="PKT"))
TODAY = CLOCK.date()
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture()
def repo() -> InMemoryParcelRepository:
    """Fresh repository for each test."""
    parcels = load_parcels(DATA_DIR)
    pickup_points = load_pickup_points(DATA_DIR)
    slots = load_slots(DATA_DIR, CLOCK)
    return InMemoryParcelRepository(parcels, slots, pickup_points)



# ── Verification service ──────────────────────────────────────────────


class TestVerifyTrackingId:
    def test_found(self, repo):
        parcel = verify_tracking_id(repo, "RD10000001")
        assert parcel is not None
        assert parcel.tracking_id == "RD10000001"

    def test_not_found(self, repo):
        assert verify_tracking_id(repo, "RD99999999") is None


class TestVerifyPhone:
    def test_correct(self, repo):
        parcel = verify_tracking_id(repo, "RD10000001")
        assert parcel is not None
        result = verify_phone(repo, parcel, parcel.phone_last4)
        assert result is True

    def test_wrong(self, repo):
        parcel = verify_tracking_id(repo, "RD10000001")
        assert parcel is not None
        result = verify_phone(repo, parcel, "0000")
        assert result is False

    def test_increments_failure_counter(self, repo):
        parcel = verify_tracking_id(repo, "RD10000001")
        verify_phone(repo, parcel, "0000")
        # Check failure counter increased.
        fresh = repo.get_parcel("RD10000001")
        assert fresh.phone_failures >= 1

    def test_locked_after_max_failures(self, repo):
        parcel = verify_tracking_id(repo, "RD10000001")
        for _ in range(3):
            verify_phone(repo, parcel, "0000")
        # Should now be locked.
        assert repo.is_parcel_locked("RD10000001") is True
        # Further attempts refuse immediately.
        result = verify_phone(repo, parcel, parcel.phone_last4)
        assert result is False


# ── Booking service ───────────────────────────────────────────────────


class TestGetAvailableSlots:
    def test_returns_non_full_slots(self, repo):
        # Day 2 (tomorrow) should have available slots.
        tomorrow = TODAY + timedelta(days=1)
        slots = get_available_slots(repo, tomorrow, CLOCK)
        assert len(slots) > 0
        for s in slots:
            assert s.booked < s.capacity

    def test_filters_by_period(self, repo):
        tomorrow = TODAY + timedelta(days=1)
        slots = get_available_slots(repo, tomorrow, CLOCK, period="morning")
        for s in slots:
            assert s.period == "morning"

    def test_today_filters_past_periods(self, repo):
        """At 14:30, morning (cutoff=12) should be excluded from today."""
        slots = get_available_slots(repo, TODAY, CLOCK)
        for s in slots:
            # Morning should be excluded (cutoff 12, clock is 14:30)
            assert s.period != "morning"

    def test_fully_booked_day_returns_empty(self, repo):
        """Day offset 3 (2026-10-29) is fully booked (all 3 periods)."""
        day_offset3 = TODAY + timedelta(days=3)
        slots = get_available_slots(repo, day_offset3, CLOCK)
        assert len(slots) == 0


class TestBookAndRelease:
    def test_book_slot(self, repo):
        tomorrow = TODAY + timedelta(days=1)
        slots = get_available_slots(repo, tomorrow, CLOCK)
        assert len(slots) > 0
        slot = slots[0]
        result = book_slot(repo, slot.slot_id, "RD10000001")
        assert result is True

    def test_release_slot(self, repo):
        tomorrow = TODAY + timedelta(days=1)
        slots = get_available_slots(repo, tomorrow, CLOCK)
        slot = slots[0]
        book_slot(repo, slot.slot_id, "RD10000001")
        result = release_slot(repo, slot.slot_id, "RD10000001")
        assert result is True


class TestRebookSlot:
    def test_rebook_success(self, repo):
        tomorrow = TODAY + timedelta(days=1)
        day4 = TODAY + timedelta(days=4)  # offset 4 has available slots
        slots_tom = get_available_slots(repo, tomorrow, CLOCK)
        slots_day4 = get_available_slots(repo, day4, CLOCK)
        assert len(slots_tom) > 0 and len(slots_day4) > 0

        old = slots_tom[0]
        new = slots_day4[0]
        book_slot(repo, old.slot_id, "RD10000001")
        result = rebook_slot(repo, old.slot_id, new.slot_id, "RD10000001")
        assert result is True
        # Verify parcel now has new slot.
        parcel = repo.get_parcel("RD10000001")
        assert parcel.current_slot_id == new.slot_id


class TestFindNearestAvailable:
    def test_finds_something(self, repo):
        slot = find_nearest_available(repo, CLOCK)
        assert slot is not None

    def test_with_period_filter(self, repo):
        slot = find_nearest_available(repo, CLOCK, period="evening")
        assert slot is not None
        assert slot.period == "evening"

    def test_falls_back_to_any_period_when_requested_period_is_unavailable(self, repo):
        slot = find_nearest_available(
            repo, CLOCK, exclude_date=TODAY, period="unavailable-period"
        )
        assert slot is not None

    def test_returns_none_when_repository_has_no_slots(self):
        class EmptySlots:
            def list_slots(self, start, end):
                return []

        assert find_nearest_available(
            EmptySlots(), CLOCK, period="morning"
        ) is None


# ── Pickup service ────────────────────────────────────────────────────


class TestPickupService:
    def test_list_all(self, repo):
        points = list_pickup_points(repo)
        assert len(points) == 5

    def test_list_filtered_by_day(self, repo):
        # Sunday — some points are closed.
        sunday = date(2026, 11, 1)
        points = list_pickup_points(repo, open_on=sunday)
        assert len(points) < 5

    def test_get_by_id(self, repo):
        points = list_pickup_points(repo)
        point = get_pickup_point(repo, points[0].point_id)
        assert point is not None
        assert point.point_id == points[0].point_id

    def test_get_not_found(self, repo):
        assert get_pickup_point(repo, "NONEXISTENT") is None


# ── Cancellation service ─────────────────────────────────────────────


class TestCancellationService:
    def test_cancel_success(self, repo):
        result = cancel_parcel(repo, "RD10000001")
        assert result is True
        parcel = repo.get_parcel("RD10000001")
        assert parcel.status.value == "cancelled"

    def test_cancel_already_cancelled(self, repo):
        cancel_parcel(repo, "RD10000001")
        result = cancel_parcel(repo, "RD10000001")
        assert result is False

    def test_cancel_not_found(self, repo):
        result = cancel_parcel(repo, "RD99999999")
        assert result is False

    def test_cancel_releases_slot(self, repo):
        # Book a slot first, then cancel.
        tomorrow = TODAY + timedelta(days=1)
        slots = get_available_slots(repo, tomorrow, CLOCK)
        slot = slots[0]
        book_slot(repo, slot.slot_id, "RD10000001")
        # Verify slot is booked.
        parcel = repo.get_parcel("RD10000001")
        assert parcel.current_slot_id == slot.slot_id

        cancel_parcel(repo, "RD10000001")
        parcel = repo.get_parcel("RD10000001")
        assert parcel.current_slot_id is None
