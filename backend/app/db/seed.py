"""Fake data for the fictional Shifa Care Clinic.

Run with ``python -m app.db.seed``. It drops and recreates every table.
All names and phone numbers are invented.
"""

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.clinic import CLINIC_NAME, OPENING_HOURS, SLOT_MINUTES
from app.clock import clinic_now
from app.db.base import Base
from app.db.models import Appointment, AppointmentStatus, Department, Doctor, Patient, Slot
from app.db.repository import generate_booking_ref
from app.db.session import SessionLocal, engine, init_db

SEED_DAYS = 21
PREBOOK_RATIO = 0.3
RNG_SEED = 42

DEPARTMENTS: dict[str, tuple[str, list[str]]] = {
    "General Medicine": (
        "Check-ups, fever, infections and everyday illness.",
        ["Dr. Areeba Qamar", "Dr. Faisal Mirza"],
    ),
    "Cardiology": (
        "Heart and blood pressure care.",
        ["Dr. Saima Rauf", "Dr. Imran Haider"],
    ),
    "Dermatology": (
        "Skin, hair and nail conditions.",
        ["Dr. Hina Shahid", "Dr. Kamran Iqbal"],
    ),
    "Pediatrics": (
        "Care for babies, children and teenagers.",
        ["Dr. Nadia Farooq", "Dr. Usman Tariq"],
    ),
    "Orthopedics": (
        "Bones, joints, back pain and sports injuries.",
        ["Dr. Bilal Aslam", "Dr. Rabia Nawaz"],
    ),
    "ENT": (
        "Ear, nose and throat.",
        ["Dr. Zain Abbas", "Dr. Mehwish Khalid"],
    ),
    "Gynecology": (
        "Women's health and pregnancy care.",
        ["Dr. Sadia Javed", "Dr. Amna Rehman"],
    ),
}

FAKE_PATIENTS: list[tuple[str, str]] = [
    ("Ali Raza", "03005550101"),
    ("Sana Malik", "03005550102"),
    ("Hamza Yousaf", "03005550103"),
    ("Ayesha Siddiqui", "03005550104"),
    ("Omar Farooq", "03005550105"),
    ("Fatima Noor", "03005550106"),
    ("Hassan Javed", "03005550107"),
    ("Mariam Ahmed", "03005550108"),
    ("Danish Ali", "03005550109"),
    ("Zara Hussain", "03005550110"),
    ("Bilal Sheikh", "03005550111"),
    ("Iqra Butt", "03005550112"),
]


@dataclass(frozen=True)
class SeedSummary:
    departments: int
    doctors: int
    slots: int
    booked: int


def slot_starts(day: date) -> list[datetime]:
    """Start times of every slot the clinic offers on ``day``."""
    starts = []
    for open_at, close_at in OPENING_HOURS[day.weekday()]:
        current = datetime.combine(day, open_at)
        close = datetime.combine(day, close_at)
        while current + timedelta(minutes=SLOT_MINUTES) <= close:
            starts.append(current)
            current += timedelta(minutes=SLOT_MINUTES)
    return starts


def seed_database(
    session: Session,
    start: date,
    days: int = SEED_DAYS,
    prebook_ratio: float = PREBOOK_RATIO,
    rng_seed: int = RNG_SEED,
) -> SeedSummary:
    """Insert departments, doctors, slots and pre-booked appointments.

    Deterministic for a given ``start`` and ``rng_seed``.
    """
    rng = random.Random(rng_seed)

    doctors: list[Doctor] = []
    for dept_name, (description, doctor_names) in DEPARTMENTS.items():
        department = Department(name=dept_name, description=description)
        session.add(department)
        for doctor_name in doctor_names:
            doctor = Doctor(name=doctor_name, department=department)
            session.add(doctor)
            doctors.append(doctor)

    patients = [Patient(name=name, phone=phone) for name, phone in FAKE_PATIENTS]
    session.add_all(patients)

    slot_count = 0
    booked_count = 0
    used_refs: set[str] = set()
    for offset in range(days):
        day = start + timedelta(days=offset)
        for start_time in slot_starts(day):
            for doctor in doctors:
                slot = Slot(
                    doctor=doctor,
                    start_time=start_time,
                    end_time=start_time + timedelta(minutes=SLOT_MINUTES),
                    is_booked=False,
                )
                session.add(slot)
                slot_count += 1
                if rng.random() < prebook_ratio:
                    ref = generate_booking_ref(rng)
                    while ref in used_refs:
                        ref = generate_booking_ref(rng)
                    used_refs.add(ref)
                    slot.is_booked = True
                    session.add(
                        Appointment(
                            booking_ref=ref,
                            patient=rng.choice(patients),
                            slot=slot,
                            status=AppointmentStatus.BOOKED,
                            created_at=datetime.combine(start, time(8)),
                        )
                    )
                    booked_count += 1

    session.commit()
    return SeedSummary(
        departments=len(DEPARTMENTS),
        doctors=len(doctors),
        slots=slot_count,
        booked=booked_count,
    )


def main() -> None:
    Base.metadata.drop_all(engine)
    init_db(engine)
    start = clinic_now().date()
    with SessionLocal() as session:
        summary = seed_database(session, start=start)
    print(
        f"Seeded {CLINIC_NAME} from {start}: {summary.departments} departments, "
        f"{summary.doctors} doctors, {summary.slots} slots, {summary.booked} pre-booked "
        f"({engine.url})"
    )


if __name__ == "__main__":
    main()
