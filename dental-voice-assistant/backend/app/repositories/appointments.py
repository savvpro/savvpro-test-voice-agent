"""Appointment repository: all DB access for bookings.

All methods take an ``AsyncSession`` so callers control transaction scope.
"""

from __future__ import annotations

from datetime import UTC, date, time

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Appointment


def _slot_end(start: time, slot_minutes: int = settings.clinic_slot_minutes) -> time:
    total = start.hour * 60 + start.minute + slot_minutes
    return time(total // 60, total % 60)


def _all_slots(day: date) -> list[tuple[time, time]]:
    """Return all (start, end) slot pairs for *day* based on clinic rules."""
    if day.weekday() not in settings.clinic_open_weekdays:
        return []
    slots = []
    current = settings.clinic_open_hour * 60
    close = settings.clinic_close_hour * 60
    while current + settings.clinic_slot_minutes <= close:
        start = time(current // 60, current % 60)
        end = time(
            (current + settings.clinic_slot_minutes) // 60,
            (current + settings.clinic_slot_minutes) % 60,
        )
        slots.append((start, end))
        current += settings.clinic_slot_minutes
    return slots


# ── Public API ────────────────────────────────────────────────────────────────


async def free_slots(session: AsyncSession, day: date) -> list[tuple[time, time]]:
    """Return list of (start, end) pairs that are not yet booked on *day*."""
    result = await session.execute(
        select(Appointment.start_time).where(
            Appointment.appointment_date == day,
            Appointment.status == "confirmed",
        )
    )
    taken: set[time] = {row[0] for row in result}
    return [(s, e) for s, e in _all_slots(day) if s not in taken]


async def create(session: AsyncSession, appointment: Appointment) -> Appointment | None:
    """Insert *appointment*. Return ``None`` on duplicate-slot IntegrityError."""
    try:
        session.add(appointment)
        await session.commit()
        await session.refresh(appointment)
        return appointment
    except IntegrityError:
        await session.rollback()
        return None


async def find_upcoming_by_phone(session: AsyncSession, phone: str) -> list[Appointment]:
    """Return all confirmed future appointments for *phone*."""
    today = date.today()
    result = await session.execute(
        select(Appointment)
        .where(
            Appointment.patient_phone == phone,
            Appointment.status == "confirmed",
            Appointment.appointment_date >= today,
        )
        .order_by(Appointment.appointment_date, Appointment.start_time)
    )
    return list(result.scalars())


async def cancel(session: AsyncSession, appointment_id: str) -> bool:
    """Mark appointment as cancelled. Return True if a row was updated."""
    from datetime import datetime

    result = await session.execute(
        update(Appointment)
        .where(Appointment.id == appointment_id, Appointment.status == "confirmed")
        .values(status="cancelled", cancelled_at=datetime.now(UTC))
        .returning(Appointment.id)
    )
    await session.commit()
    return result.fetchone() is not None


async def reschedule(
    session: AsyncSession,
    old_id: str,
    new_appointment: Appointment,
) -> Appointment | None:
    """Atomically cancel *old_id* and create *new_appointment*.

    Returns new Appointment on success, None if the new slot is taken or old not found.
    """
    from datetime import datetime

    result = await session.execute(
        select(Appointment).where(Appointment.id == old_id, Appointment.status == "confirmed")
    )
    old = result.scalar_one_or_none()
    if old is None:
        return None

    if not new_appointment.patient_name:
        new_appointment.patient_name = old.patient_name
    if not new_appointment.patient_phone:
        new_appointment.patient_phone = old.patient_phone
    if not new_appointment.service:
        new_appointment.service = old.service

    try:
        async with session.begin_nested():
            old.status = "rescheduled"
            old.cancelled_at = datetime.now(UTC)
            session.add(new_appointment)
            await session.flush()
        await session.commit()
        await session.refresh(new_appointment)
        return new_appointment
    except IntegrityError:
        await session.rollback()
        return None


async def list_by_day(session: AsyncSession, day: date) -> list[Appointment]:
    """Return all confirmed appointments on *day*, ordered by start time."""
    result = await session.execute(
        select(Appointment)
        .where(
            Appointment.appointment_date == day,
            Appointment.status == "confirmed",
        )
        .order_by(Appointment.start_time)
    )
    return list(result.scalars())
