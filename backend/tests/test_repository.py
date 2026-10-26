"""Tests for the data layer: loader, repository, and session store.

All slot-related tests use the ``frozen_clock`` fixture from conftest so
dates are deterministic.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.data.loader import (
    generate_slots,
    load_parcels,
    load_pickup_points,
    load_slots,
)
from app.data.repository import InMemoryParcelRepository, InMemorySessionStore
from app.models.parcel import (
    DeliverySlot,
    Parcel,
    ParcelStatus,
    Period,
    PickupPoint,
    SlotTemplate,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def clock() -> datetime:
    """Monday 2026-10-26 14:30 PKT — same as frozen_clock in conftest."""
    return datetime(2026, 10, 26, 14, 30, tzinfo=timezone(timedelta(hours=5), name="PKT"))


@pytest.fixture()
def parcels() -> list[Parcel]:
    return load_parcels(DATA_DIR)


@pytest.fixture()
def pickup_points() -> list[PickupPoint]:
    return load_pickup_points(DATA_DIR)


@pytest.fixture()
def slots(clock: datetime) -> list[DeliverySlot]:
    return load_slots(DATA_DIR, clock)


@pytest.fixture()
def repo(
    parcels: list[Parcel],
    slots: list[DeliverySlot],
    pickup_points: list[PickupPoint],
) -> InMemoryParcelRepository:
    return InMemoryParcelRepository(
        parcels=parcels,
        slots=slots,
        pickup_points=pickup_points,
        max_phone_attempts=3,
    )


@pytest.fixture()
def session_store() -> InMemorySessionStore:
    return InMemorySessionStore()


# ── Loader tests ──────────────────────────────────────────────────────


class TestLoadParcels:
    """Verify parcels.json loads correctly."""

    def test_loads_at_least_21(self, parcels: list[Parcel]):
        assert len(parcels) >= 21

    def test_all_statuses_present(self, parcels: list[Parcel]):
        statuses = {p.status for p in parcels}
        for s in ParcelStatus:
            assert s in statuses, f"Missing status {s.value}"

    def test_status_counts(self, parcels: list[Parcel]):
        counts: dict[ParcelStatus, int] = {}
        for p in parcels:
            counts[p.status] = counts.get(p.status, 0) + 1
        assert counts[ParcelStatus.FAILED_ATTEMPT] >= 8
        assert counts[ParcelStatus.IN_TRANSIT] >= 3
        assert counts[ParcelStatus.OUT_FOR_DELIVERY] >= 3
        assert counts[ParcelStatus.DELIVERED] >= 3
        assert counts[ParcelStatus.CANCELLED] >= 2
        assert counts[ParcelStatus.RETURNED_TO_SENDER] >= 2

    def test_tracking_ids_unique(self, parcels: list[Parcel]):
        ids = [p.tracking_id for p in parcels]
        assert len(ids) == len(set(ids))

    def test_tracking_id_format(self, parcels: list[Parcel]):
        for p in parcels:
            assert p.tracking_id.startswith("RD")
            assert len(p.tracking_id) == 10
            assert p.tracking_id[2:].isdigit()

    def test_phone_last4_format(self, parcels: list[Parcel]):
        for p in parcels:
            assert len(p.phone_last4) == 4
            assert p.phone_last4.isdigit()


class TestLoadPickupPoints:
    """Verify pickup_points.json loads correctly."""

    def test_loads_5(self, pickup_points: list[PickupPoint]):
        assert len(pickup_points) == 5

    def test_ids_unique(self, pickup_points: list[PickupPoint]):
        ids = [pp.point_id for pp in pickup_points]
        assert len(ids) == len(set(ids))

    def test_has_weekday_only_point(self, pickup_points: list[PickupPoint]):
        """At least one point is closed on weekends."""
        weekday_only = [
            pp for pp in pickup_points
            if "saturday" not in pp.open_days and "sunday" not in pp.open_days
        ]
        assert len(weekday_only) >= 1

    def test_has_seven_day_point(self, pickup_points: list[PickupPoint]):
        """At least one point is open every day."""
        seven_day = [pp for pp in pickup_points if len(pp.open_days) == 7]
        assert len(seven_day) >= 1


class TestSlotGeneration:
    """Verify the slot grid is generated from the clock."""

    def test_generates_21_slots(self, slots: list[DeliverySlot]):
        assert len(slots) == 21  # 7 days × 3 periods

    def test_dates_span_7_days(self, slots: list[DeliverySlot], clock: datetime):
        today = clock.date()
        dates = sorted({s.date for s in slots})
        assert len(dates) == 7
        assert dates[0] == today
        assert dates[-1] == today + timedelta(days=6)

    def test_each_day_has_3_periods(self, slots: list[DeliverySlot]):
        by_date: dict[date, set[str]] = {}
        for s in slots:
            by_date.setdefault(s.date, set()).add(s.period.value)
        for d, periods in by_date.items():
            assert periods == {"morning", "afternoon", "evening"}, (
                f"Date {d} missing periods: {periods}"
            )

    def test_slot_id_format(self, slots: list[DeliverySlot]):
        for s in slots:
            assert s.slot_id.startswith("SLOT-")
            assert s.date.isoformat() in s.slot_id
            assert s.period.value in s.slot_id

    def test_default_capacity(self, slots: list[DeliverySlot]):
        for s in slots:
            assert s.capacity == 3

    def test_day1_morning_fully_booked(
        self, slots: list[DeliverySlot], clock: datetime
    ):
        """Day offset 1 morning must be pre-booked to capacity."""
        day1 = clock.date() + timedelta(days=1)
        morning = [
            s for s in slots
            if s.date == day1 and s.period == Period.MORNING
        ]
        assert len(morning) == 1
        assert morning[0].is_full

    def test_day3_fully_booked(
        self, slots: list[DeliverySlot], clock: datetime
    ):
        """Day offset 3 (all 3 periods) must be fully booked."""
        day3 = clock.date() + timedelta(days=3)
        day3_slots = [s for s in slots if s.date == day3]
        assert len(day3_slots) == 3
        for s in day3_slots:
            assert s.is_full, f"Day 3 {s.period.value} not full: {s.booked}/{s.capacity}"

    def test_day5_evening_nearly_full(
        self, slots: list[DeliverySlot], clock: datetime
    ):
        """Day offset 5 evening has 2 of 3 booked."""
        day5 = clock.date() + timedelta(days=5)
        evening = [
            s for s in slots
            if s.date == day5 and s.period == Period.EVENING
        ]
        assert len(evening) == 1
        assert evening[0].booked == 2
        assert evening[0].available == 1

    def test_generate_slots_with_custom_template(self, clock: datetime):
        """generate_slots works with arbitrary templates."""
        template = SlotTemplate(default_capacity=5, pre_booked=[])
        result = generate_slots(template, clock)
        assert len(result) == 21
        assert all(s.capacity == 5 for s in result)
        assert all(s.booked == 0 for s in result)


# ── Repository: parcel queries ────────────────────────────────────────


class TestParcelRepo:
    def test_get_parcel_found(self, repo: InMemoryParcelRepository):
        p = repo.get_parcel("RD30000001")
        assert p is not None
        assert p.tracking_id == "RD30000001"
        assert p.status == ParcelStatus.FAILED_ATTEMPT

    def test_get_parcel_not_found(self, repo: InMemoryParcelRepository):
        assert repo.get_parcel("RD99999999") is None

    def test_get_parcel_case_sensitive(self, repo: InMemoryParcelRepository):
        """Tracking IDs are stored uppercase; lowercase should not match."""
        assert repo.get_parcel("rd30000001") is None


# ── Repository: slot operations ───────────────────────────────────────


class TestSlotRepo:
    def test_list_slots_full_range(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        today = clock.date()
        end = today + timedelta(days=6)
        result = repo.list_slots(today, end)
        assert len(result) == 21

    def test_list_slots_single_day(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        today = clock.date()
        result = repo.list_slots(today, today)
        assert len(result) == 3

    def test_list_slots_out_of_range(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        far = clock.date() + timedelta(days=30)
        result = repo.list_slots(far, far)
        assert len(result) == 0

    def test_get_slot_by_id(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        today_str = clock.date().isoformat()
        slot = repo.get_slot(f"SLOT-{today_str}-morning")
        assert slot is not None
        assert slot.period == Period.MORNING

    def test_get_slot_not_found(self, repo: InMemoryParcelRepository):
        assert repo.get_slot("SLOT-nonexistent") is None


# ── Repository: booking ───────────────────────────────────────────────


class TestBooking:
    def test_book_slot_success(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        today_str = clock.date().isoformat()
        slot_id = f"SLOT-{today_str}-morning"
        slot_before = repo.get_slot(slot_id)
        assert slot_before is not None
        booked_before = slot_before.booked

        ok = repo.book_slot(slot_id, "RD30000001")
        assert ok is True

        slot_after = repo.get_slot(slot_id)
        assert slot_after is not None
        assert slot_after.booked == booked_before + 1

        parcel = repo.get_parcel("RD30000001")
        assert parcel is not None
        assert parcel.current_slot_id == slot_id

    def test_book_slot_full(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        """Booking a fully-booked slot returns False."""
        day1 = clock.date() + timedelta(days=1)
        slot_id = f"SLOT-{day1.isoformat()}-morning"
        slot = repo.get_slot(slot_id)
        assert slot is not None
        assert slot.is_full

        ok = repo.book_slot(slot_id, "RD30000001")
        assert ok is False

    def test_book_slot_nonexistent(self, repo: InMemoryParcelRepository):
        ok = repo.book_slot("SLOT-fake", "RD30000001")
        assert ok is False

    def test_book_slot_nonexistent_parcel(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        today_str = clock.date().isoformat()
        ok = repo.book_slot(f"SLOT-{today_str}-morning", "RD99999999")
        assert ok is False

    def test_release_slot_success(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        today_str = clock.date().isoformat()
        slot_id = f"SLOT-{today_str}-afternoon"
        repo.book_slot(slot_id, "RD30000002")

        ok = repo.release_slot(slot_id, "RD30000002")
        assert ok is True

        slot = repo.get_slot(slot_id)
        assert slot is not None
        assert slot.booked == 0

        parcel = repo.get_parcel("RD30000002")
        assert parcel is not None
        assert parcel.current_slot_id is None

    def test_release_slot_not_booked(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        """Releasing a slot the parcel doesn't hold returns False."""
        today_str = clock.date().isoformat()
        slot_id = f"SLOT-{today_str}-afternoon"
        ok = repo.release_slot(slot_id, "RD30000002")
        assert ok is False

    def test_book_release_book_cycle(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        today_str = clock.date().isoformat()
        slot_id = f"SLOT-{today_str}-evening"

        assert repo.book_slot(slot_id, "RD30000003") is True
        assert repo.release_slot(slot_id, "RD30000003") is True
        assert repo.book_slot(slot_id, "RD30000003") is True

    def test_rebook_slot_atomic(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        """Rebook atomically releases old and books new."""
        today = clock.date()
        old_id = f"SLOT-{today.isoformat()}-morning"
        new_id = f"SLOT-{today.isoformat()}-evening"

        # Book the old slot first.
        assert repo.book_slot(old_id, "RD30000004") is True
        old_booked = repo.get_slot(old_id).booked  # type: ignore[union-attr]

        ok = repo.rebook_slot(old_id, new_id, "RD30000004")
        assert ok is True

        # Old slot count decremented.
        assert repo.get_slot(old_id).booked == old_booked - 1  # type: ignore[union-attr]
        # New slot count incremented.
        assert repo.get_slot(new_id).booked == 1  # type: ignore[union-attr]
        # Parcel points to new slot.
        p = repo.get_parcel("RD30000004")
        assert p is not None
        assert p.current_slot_id == new_id

    def test_rebook_fails_if_new_slot_full(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        """If the new slot is full, the old slot stays unchanged."""
        today = clock.date()
        old_id = f"SLOT-{today.isoformat()}-morning"
        day1_morning = f"SLOT-{(today + timedelta(days=1)).isoformat()}-morning"

        assert repo.book_slot(old_id, "RD30000005") is True

        # Day+1 morning is fully booked.
        ok = repo.rebook_slot(old_id, day1_morning, "RD30000005")
        assert ok is False

        # Old slot unchanged.
        p = repo.get_parcel("RD30000005")
        assert p is not None
        assert p.current_slot_id == old_id

    def test_concurrent_booking_capacity_honoured(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        """Race multiple threads; total bookings must not exceed capacity."""
        day5 = clock.date() + timedelta(days=5)
        slot_id = f"SLOT-{day5.isoformat()}-evening"

        # This slot starts with 2 booked, capacity 3 → 1 remaining.
        slot = repo.get_slot(slot_id)
        assert slot is not None
        assert slot.available == 1

        results: list[bool] = []
        lock = threading.Lock()

        def try_book(tid: str) -> None:
            ok = repo.book_slot(slot_id, tid)
            with lock:
                results.append(ok)

        threads = [
            threading.Thread(target=try_book, args=(f"RD3000000{i}",))
            for i in range(1, 5)  # 4 threads
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 1 should have succeeded.
        assert results.count(True) == 1
        assert results.count(False) == 3

        # Slot is now full.
        assert repo.get_slot(slot_id).is_full  # type: ignore[union-attr]


# ── Repository: pickup points ─────────────────────────────────────────


class TestPickupPoints:
    def test_list_all(self, repo: InMemoryParcelRepository):
        assert len(repo.list_pickup_points()) == 5

    def test_get_by_id(self, repo: InMemoryParcelRepository):
        pp = repo.get_pickup_point("PP-001")
        assert pp is not None
        assert pp.name == "Islamabad I-8 Markaz Depot"

    def test_get_not_found(self, repo: InMemoryParcelRepository):
        assert repo.get_pickup_point("PP-999") is None

    def test_filter_open_on_weekday(self, repo: InMemoryParcelRepository):
        """On a Wednesday all 5 points should be open."""
        wednesday = date(2026, 10, 28)
        open_pts = repo.list_pickup_points(open_on=wednesday)
        assert len(open_pts) == 5

    def test_filter_open_on_sunday(self, repo: InMemoryParcelRepository):
        """On Sunday only the Lahore hub (7-day) should be open."""
        sunday = date(2026, 11, 1)
        open_pts = repo.list_pickup_points(open_on=sunday)
        names = [pp.name for pp in open_pts]
        assert "Lahore Gulberg Collection Hub" in names
        # Islamabad and Peshawar points are weekday-only.
        assert "Islamabad I-8 Markaz Depot" not in names
        assert "Peshawar University Road Collection Point" not in names

    def test_filter_open_on_saturday(self, repo: InMemoryParcelRepository):
        """On Saturday, Lahore, Karachi, and Rawalpindi points should be open."""
        saturday = date(2026, 10, 31)
        open_pts = repo.list_pickup_points(open_on=saturday)
        names = {pp.name for pp in open_pts}
        assert "Lahore Gulberg Collection Hub" in names
        assert "Karachi Clifton Express Desk" in names
        assert "Rawalpindi Saddar Mini Depot" in names
        assert "Islamabad I-8 Markaz Depot" not in names

    def test_pickup_point_is_open_on_method(self):
        pp = PickupPoint(
            point_id="T1",
            name="Test",
            address="1 Test St",
            open_days=["monday", "wednesday", "friday"],
            open_hours="09:00-17:00",
        )
        assert pp.is_open_on(date(2026, 10, 26)) is True  # Monday
        assert pp.is_open_on(date(2026, 10, 27)) is False  # Tuesday


# ── Repository: cancel ────────────────────────────────────────────────


class TestCancelParcel:
    def test_cancel_success(self, repo: InMemoryParcelRepository):
        ok = repo.cancel_parcel("RD30000006")
        assert ok is True
        p = repo.get_parcel("RD30000006")
        assert p is not None
        assert p.status == ParcelStatus.CANCELLED

    def test_cancel_releases_slot(
        self, repo: InMemoryParcelRepository, clock: datetime
    ):
        today_str = clock.date().isoformat()
        slot_id = f"SLOT-{today_str}-morning"

        repo.book_slot(slot_id, "RD30000007")
        slot_before = repo.get_slot(slot_id)
        assert slot_before is not None
        booked_before = slot_before.booked

        repo.cancel_parcel("RD30000007")

        slot_after = repo.get_slot(slot_id)
        assert slot_after is not None
        assert slot_after.booked == booked_before - 1

        p = repo.get_parcel("RD30000007")
        assert p is not None
        assert p.current_slot_id is None

    def test_cancel_already_cancelled(self, repo: InMemoryParcelRepository):
        assert repo.cancel_parcel("RD50000001") is False  # Already cancelled

    def test_cancel_not_found(self, repo: InMemoryParcelRepository):
        assert repo.cancel_parcel("RD99999999") is False


# ── Repository: phone failures ────────────────────────────────────────


class TestPhoneFailures:
    def test_initial_state(self, repo: InMemoryParcelRepository):
        assert repo.is_parcel_locked("RD30000001") is False

    def test_increment(self, repo: InMemoryParcelRepository):
        count = repo.increment_phone_failures("RD30000001")
        assert count == 1
        assert repo.is_parcel_locked("RD30000001") is False

    def test_lock_after_max_attempts(self, repo: InMemoryParcelRepository):
        for _ in range(3):
            repo.increment_phone_failures("RD30000001")
        assert repo.is_parcel_locked("RD30000001") is True

    def test_locked_stays_locked(self, repo: InMemoryParcelRepository):
        for _ in range(3):
            repo.increment_phone_failures("RD30000002")
        assert repo.is_parcel_locked("RD30000002") is True
        # Even after more increments.
        repo.increment_phone_failures("RD30000002")
        assert repo.is_parcel_locked("RD30000002") is True

    def test_increment_nonexistent(self, repo: InMemoryParcelRepository):
        assert repo.increment_phone_failures("RD99999999") == 0

    def test_is_locked_nonexistent(self, repo: InMemoryParcelRepository):
        assert repo.is_parcel_locked("RD99999999") is False

    def test_different_parcels_independent(
        self, repo: InMemoryParcelRepository
    ):
        """Failures on one parcel do not affect another."""
        for _ in range(3):
            repo.increment_phone_failures("RD30000003")
        assert repo.is_parcel_locked("RD30000003") is True
        assert repo.is_parcel_locked("RD30000004") is False


# ── Session store ─────────────────────────────────────────────────────


class TestSessionStore:
    def test_create_session(self, session_store: InMemorySessionStore):
        s = session_store.create_session()
        assert s.session_id is not None
        assert s.ended is False

    def test_get_session_found(self, session_store: InMemorySessionStore):
        s = session_store.create_session()
        found = session_store.get_session(s.session_id)
        assert found is not None
        assert found.session_id == s.session_id

    def test_get_session_not_found(self, session_store: InMemorySessionStore):
        assert session_store.get_session("nonexistent") is None

    def test_save_session(self, session_store: InMemorySessionStore):
        s = session_store.create_session()
        s.ended = True
        session_store.save_session(s)
        found = session_store.get_session(s.session_id)
        assert found is not None
        assert found.ended is True

    def test_delete_session(self, session_store: InMemorySessionStore):
        s = session_store.create_session()
        session_store.delete_session(s.session_id)
        found = session_store.get_session(s.session_id)
        assert found is not None
        assert found.ended is True

    def test_unique_session_ids(self, session_store: InMemorySessionStore):
        ids = {session_store.create_session().session_id for _ in range(50)}
        assert len(ids) == 50

    def test_session_has_lock(self, session_store: InMemorySessionStore):
        s = session_store.create_session()
        assert hasattr(s, "lock")
        assert isinstance(s.lock, type(threading.Lock()))
