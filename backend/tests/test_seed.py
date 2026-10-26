from datetime import time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Appointment, AppointmentStatus, Department, Doctor, Slot
from app.db.seed import seed_database, slot_starts
from app.db.session import create_db_engine
from tests.conftest import REF_MONDAY


def _fresh_session():
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_seed_counts(seeded):
    assert seeded.scalar(select(func.count()).select_from(Department)) == 7
    assert seeded.scalar(select(func.count()).select_from(Doctor)) == 14
    # Per doctor: 5 weekdays x 21 slots + Saturday 12 slots + Sunday 0 = 117.
    assert seeded.scalar(select(func.count()).select_from(Slot)) == 14 * 117


def test_every_department_has_two_doctors(seeded):
    for department in seeded.scalars(select(Department)):
        assert len(department.doctors) == 2


def test_opening_hours():
    monday = slot_starts(REF_MONDAY)
    assert monday[0].time() == time(9)
    assert monday[-1].time() == time(16, 40)
    assert not any(time(13) <= s.time() < time(14) for s in monday)

    saturday = slot_starts(REF_MONDAY + timedelta(days=5))
    assert saturday[0].time() == time(9)
    assert saturday[-1].time() == time(12, 40)

    assert slot_starts(REF_MONDAY + timedelta(days=6)) == []


def test_slots_are_twenty_minutes(seeded):
    for slot in seeded.scalars(select(Slot).limit(200)):
        assert slot.end_time - slot.start_time == timedelta(minutes=20)


def test_prebooked_ratio_and_consistency():
    with _fresh_session() as session:
        summary = seed_database(session, start=REF_MONDAY)  # defaults: 21 days, 30%
        assert 0.25 <= summary.booked / summary.slots <= 0.35

        booked_slot_ids = set(session.scalars(select(Slot.id).where(Slot.is_booked.is_(True))))
        appointment_slot_ids = set(
            session.scalars(
                select(Appointment.slot_id).where(Appointment.status == AppointmentStatus.BOOKED)
            )
        )
        assert booked_slot_ids == appointment_slot_ids
        assert len(booked_slot_ids) == summary.booked


def test_seed_is_deterministic():
    def snapshot():
        with _fresh_session() as session:
            seed_database(session, start=REF_MONDAY)
            return session.execute(
                select(Appointment.booking_ref, Slot.doctor_id, Slot.start_time)
                .join(Appointment.slot)
                .order_by(Appointment.booking_ref)
            ).all()

    assert snapshot() == snapshot()
