"""Unit tests — appointments repository (in-memory SQLite)."""

from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Appointment
from app.repositories import appointments as repo


def _make_appt(
    day: date,
    start: time,
    end: time,
    name: str = "Test User",
    phone: str = "03000000001",
    service: str = "checkup",
) -> Appointment:
    return Appointment(
        patient_name=name,
        patient_phone=phone,
        service=service,
        appointment_date=day,
        start_time=start,
        end_time=end,
    )


today = date.today()
tomorrow = today + timedelta(days=1)
# Choose a weekday (Mon–Sat)
while tomorrow.weekday() == 6:  # skip Sunday
    tomorrow += timedelta(days=1)


@pytest.mark.asyncio
async def test_create_and_free_slots(db_session: AsyncSession) -> None:
    slots_before = await repo.free_slots(db_session, tomorrow)
    assert len(slots_before) > 0

    appt = _make_appt(tomorrow, time(9, 0), time(9, 30))
    result = await repo.create(db_session, appt)
    assert result is not None
    assert result.id is not None

    slots_after = await repo.free_slots(db_session, tomorrow)
    assert len(slots_after) == len(slots_before) - 1
    assert (time(9, 0), time(9, 30)) not in slots_after


@pytest.mark.asyncio
async def test_create_returns_none_on_duplicate(db_session: AsyncSession) -> None:
    appt1 = _make_appt(tomorrow, time(10, 0), time(10, 30))
    appt2 = _make_appt(tomorrow, time(10, 0), time(10, 30), name="Other User")

    r1 = await repo.create(db_session, appt1)
    r2 = await repo.create(db_session, appt2)

    assert r1 is not None
    assert r2 is None  # duplicate slot


@pytest.mark.asyncio
async def test_find_upcoming_by_phone(db_session: AsyncSession) -> None:
    phone = "03000000099"
    appt = _make_appt(tomorrow, time(11, 0), time(11, 30), phone=phone)
    await repo.create(db_session, appt)

    results = await repo.find_upcoming_by_phone(db_session, phone)
    assert len(results) == 1
    assert results[0].patient_phone == phone


@pytest.mark.asyncio
async def test_find_upcoming_by_phone_no_past(db_session: AsyncSession) -> None:
    """Past appointments should not appear."""
    phone = "03000000088"
    past = today - timedelta(days=1)
    appt = _make_appt(past, time(9, 0), time(9, 30), phone=phone)
    # Insert directly to bypass date restriction in repo
    db_session.add(appt)
    await db_session.commit()

    results = await repo.find_upcoming_by_phone(db_session, phone)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_cancel(db_session: AsyncSession) -> None:
    appt = _make_appt(tomorrow, time(14, 0), time(14, 30))
    created = await repo.create(db_session, appt)
    assert created is not None

    ok = await repo.cancel(db_session, created.id)
    assert ok is True

    # Cancelled slot should now be free again
    slots = await repo.free_slots(db_session, tomorrow)
    assert (time(14, 0), time(14, 30)) in slots


@pytest.mark.asyncio
async def test_cancel_nonexistent(db_session: AsyncSession) -> None:
    ok = await repo.cancel(db_session, "nonexistent-id")
    assert ok is False


@pytest.mark.asyncio
async def test_list_by_day(db_session: AsyncSession) -> None:
    appt = _make_appt(tomorrow, time(15, 0), time(15, 30))
    await repo.create(db_session, appt)

    results = await repo.list_by_day(db_session, tomorrow)
    assert any(a.start_time == time(15, 0) for a in results)


@pytest.mark.asyncio
async def test_free_slots_sunday_empty(db_session: AsyncSession) -> None:
    """Sunday should return zero free slots."""
    # Find next Sunday
    d = tomorrow
    while d.weekday() != 6:
        d += timedelta(days=1)
    slots = await repo.free_slots(db_session, d)
    assert slots == []
