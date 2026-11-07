"""Idempotent seed: create ~15 fake appointments over the next 2 weeks.

Run via::

    python -m app.db.seed

or call ``await seed(session)`` from lifespan.
"""

from __future__ import annotations

import asyncio
import random
from datetime import date, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import async_session_factory, engine
from app.db.models import Appointment, Base

# Fake patient data — no real people
_PATIENTS = [
    ("Sara Khan", "03000000001"),
    ("Ali Ahmed", "03000000002"),
    ("Hira Malik", "03000000003"),
    ("Usman Raza", "03000000004"),
    ("Fatima Noor", "03000000005"),
    ("Bilal Chaudhry", "03000000006"),
    ("Zara Siddiqui", "03000000007"),
    ("Hamza Iqbal", "03000000008"),
]

_SERVICES = [
    "cleaning",
    "checkup",
    "filling",
    "whitening",
    "root canal",
    "braces consultation",
]

# Slots: 09:00 – 17:00 in 30-min increments (Mon–Sat)
_SLOT_HOURS = list(range(9, 17))  # 09, 10, … 16


def _open_days_in_next_two_weeks(today: date) -> list[date]:
    days = []
    for offset in range(1, 15):
        d = today + timedelta(days=offset)
        if d.weekday() != 6:  # skip Sunday
            days.append(d)
    return days


async def seed(session: AsyncSession) -> None:
    """Insert ~15 appointments; skip if already present (idempotent)."""
    today = date.today()
    open_days = _open_days_in_next_two_weeks(today)

    rng = random.Random(42)  # deterministic seed for reproducibility
    booked_slots: set[tuple[date, time]] = set()

    # Load already-booked confirmed slots in the window
    result = await session.execute(
        select(Appointment.appointment_date, Appointment.start_time).where(
            Appointment.status == "confirmed",
            Appointment.appointment_date >= today,
            Appointment.appointment_date <= today + timedelta(days=14),
        )
    )
    for row in result:
        booked_slots.add((row.appointment_date, row.start_time))

    if len(booked_slots) >= 15:
        print(f"Seed: database already contains {len(booked_slots)} appointments; skipping.")
        return

    created = 0
    attempts = 0
    while created < 15 and attempts < 200:
        attempts += 1
        day = rng.choice(open_days)
        hour = rng.choice(_SLOT_HOURS)
        half = rng.choice([0, 30])
        start = time(hour, half)
        end_hour, end_min = divmod(hour * 60 + half + 30, 60)
        end = time(end_hour, end_min)

        slot = (day, start)
        if slot in booked_slots:
            continue

        name, phone = rng.choice(_PATIENTS)
        service = rng.choice(_SERVICES)
        session.add(
            Appointment(
                patient_name=name,
                patient_phone=phone,
                service=service,
                appointment_date=day,
                start_time=start,
                end_time=end,
                status="confirmed",
            )
        )
        booked_slots.add(slot)
        created += 1

    await session.commit()
    print(f"Seed: inserted {created} appointments.")


async def _main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(_main())
