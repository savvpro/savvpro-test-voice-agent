"""All database queries live here.

Times passed in and returned are naive clinic-local datetimes (see models.py).
Functions that look at "the future" take an optional ``now`` so tests can pin
the clock; it defaults to the current clinic-local time.
"""

import random
from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from sqlalchemy import Select, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager

from app.clock import clinic_now
from app.db.models import Appointment, AppointmentStatus, Department, Doctor, Patient, Slot

# No 0/O or 1/I so references survive being read aloud and transcribed.
BOOKING_REF_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
BOOKING_REF_PREFIX = "SC-"
BOOKING_REF_LENGTH = 4

_system_random = random.SystemRandom()


class RepositoryError(Exception):
    pass


class SlotUnavailableError(RepositoryError):
    """The slot does not exist, is in the past, or is already booked."""


class AppointmentNotFoundError(RepositoryError):
    """No active (booked) appointment matches."""


def generate_booking_ref(rng: random.Random | None = None) -> str:
    rng = rng or _system_random
    return BOOKING_REF_PREFIX + "".join(
        rng.choice(BOOKING_REF_ALPHABET) for _ in range(BOOKING_REF_LENGTH)
    )


# --- Departments & doctors -------------------------------------------------


def list_departments(session: Session) -> list[Department]:
    return list(session.scalars(select(Department).order_by(Department.name)))


def get_department(session: Session, name: str) -> Department | None:
    return session.scalar(select(Department).where(func.lower(Department.name) == name.lower()))


def find_doctors(session: Session, department: str | None = None) -> list[Doctor]:
    stmt = (
        select(Doctor)
        .join(Doctor.department)
        .options(contains_eager(Doctor.department))
        .order_by(Doctor.name)
    )
    if department is not None:
        stmt = stmt.where(func.lower(Department.name) == department.lower())
    return list(session.scalars(stmt))


# --- Slots -----------------------------------------------------------------


def _free_slots_stmt(department: str, doctor: str | None, now: datetime) -> Select[tuple[Slot]]:
    stmt = (
        select(Slot)
        .join(Slot.doctor)
        .join(Doctor.department)
        .options(contains_eager(Slot.doctor).contains_eager(Doctor.department))
        .where(
            Slot.is_booked.is_(False),
            Slot.start_time > now,
            func.lower(Department.name) == department.lower(),
        )
    )
    if doctor is not None:
        stmt = stmt.where(func.lower(Doctor.name) == doctor.lower())
    return stmt


def find_free_slots(
    session: Session,
    department: str,
    day: date,
    time_range: tuple[time, time] | None = None,
    doctor: str | None = None,
    limit: int = 3,
    now: datetime | None = None,
) -> list[Slot]:
    """Free future slots on ``day``, earliest first.

    ``time_range`` is (start, end) and matches slots *starting* in [start, end).
    """
    now = now or clinic_now()
    if time_range is None:
        window_start = datetime.combine(day, time.min)
        window_end = window_start + timedelta(days=1)
    else:
        window_start = datetime.combine(day, time_range[0])
        window_end = datetime.combine(day, time_range[1])

    stmt = (
        _free_slots_stmt(department, doctor, now)
        .where(Slot.start_time >= window_start, Slot.start_time < window_end)
        .order_by(Slot.start_time, Doctor.name)
        .limit(limit)
    )
    return list(session.scalars(stmt))


def find_nearest_free_slots(
    session: Session,
    department: str,
    around_datetime: datetime,
    limit: int = 3,
    now: datetime | None = None,
    doctor: str | None = None,
) -> list[Slot]:
    """Free future slots in the department closest in time to ``around_datetime``.

    With ``doctor``, that doctor's nearest slots come first and other doctors in the
    department only fill the remaining places.
    """
    now = now or clinic_now()
    slots = session.scalars(_free_slots_stmt(department, None, now)).all()

    def rank(s: Slot):
        preferred = doctor is None or s.doctor.name.lower() == doctor.lower()
        return (
            not preferred,
            abs((s.start_time - around_datetime).total_seconds()),
            s.start_time,
            s.doctor.name,
        )

    return sorted(slots, key=rank)[:limit]


def _claim_slot(session: Session, slot_id: int, now: datetime) -> None:
    # Conditional UPDATE: only one caller can flip is_booked from False to True.
    result = session.execute(
        update(Slot)
        .where(Slot.id == slot_id, Slot.is_booked.is_(False), Slot.start_time > now)
        .values(is_booked=True)
    )
    if result.rowcount != 1:
        raise SlotUnavailableError(f"slot {slot_id} is not available")


# --- Appointments ----------------------------------------------------------


def _new_booking_ref(session: Session) -> str:
    while True:
        ref = generate_booking_ref()
        if session.scalar(select(Appointment.id).where(Appointment.booking_ref == ref)) is None:
            return ref


def _get_or_create_patient(session: Session, name: str, phone: str) -> Patient:
    patient = session.scalar(select(Patient).where(Patient.phone == phone))
    if patient is None:
        patient = Patient(name=name, phone=phone)
        session.add(patient)
    else:
        patient.name = name
    return patient


def book_slot(
    session: Session, slot_id: int, name: str, phone: str, now: datetime | None = None
) -> Appointment:
    """Book a slot in one transaction. Raises SlotUnavailableError if it was taken."""
    now = now or clinic_now()
    try:
        _claim_slot(session, slot_id, now)
        appointment = Appointment(
            booking_ref=_new_booking_ref(session),
            patient=_get_or_create_patient(session, name, phone),
            slot_id=slot_id,
            status=AppointmentStatus.BOOKED,
            created_at=now,
        )
        session.add(appointment)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise SlotUnavailableError(f"slot {slot_id} is not available") from exc
    except Exception:
        session.rollback()
        raise
    return appointment


def get_appointment(
    session: Session,
    ref: str | None = None,
    phone: str | None = None,
    now: datetime | None = None,
) -> Appointment | None:
    """Look up by booking reference (any status) or by phone.

    By phone it returns the caller's soonest upcoming booked appointment.
    """
    if ref is not None:
        return session.scalar(
            select(Appointment).where(Appointment.booking_ref == ref.strip().upper())
        )
    if phone is not None:
        now = now or clinic_now()
        return session.scalar(
            select(Appointment)
            .join(Appointment.patient)
            .join(Appointment.slot)
            .where(
                Patient.phone == phone,
                Appointment.status == AppointmentStatus.BOOKED,
                Slot.start_time > now,
            )
            .order_by(Slot.start_time)
            .limit(1)
        )
    raise ValueError("get_appointment needs a ref or a phone")


def _get_active_appointment(session: Session, ref: str) -> Appointment:
    appointment = get_appointment(session, ref=ref)
    if appointment is None or appointment.status != AppointmentStatus.BOOKED:
        raise AppointmentNotFoundError(f"no active appointment with ref {ref!r}")
    return appointment


def cancel_appointment(session: Session, ref: str) -> Appointment:
    try:
        appointment = _get_active_appointment(session, ref)
        appointment.status = AppointmentStatus.CANCELLED
        appointment.slot.is_booked = False
        session.commit()
    except Exception:
        session.rollback()
        raise
    return appointment


def reschedule_appointment(
    session: Session, ref: str, new_slot_id: int, now: datetime | None = None
) -> Appointment:
    """Move an active appointment to a new slot atomically; the old slot is freed."""
    now = now or clinic_now()
    try:
        appointment = _get_active_appointment(session, ref)
        _claim_slot(session, new_slot_id, now)
        appointment.slot.is_booked = False
        appointment.slot_id = new_slot_id
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise SlotUnavailableError(f"slot {new_slot_id} is not available") from exc
    except Exception:
        session.rollback()
        raise
    session.refresh(appointment)
    return appointment


# --- Admin views (UI side panel) ----------------------------------------------


def list_slots(
    session: Session,
    department: str | None = None,
    day: date | None = None,
    limit: int = 200,
) -> list[Slot]:
    """Slots (free and booked) in time order, optionally for one department and day."""
    stmt = (
        select(Slot)
        .join(Slot.doctor)
        .join(Doctor.department)
        .options(contains_eager(Slot.doctor).contains_eager(Doctor.department))
        .order_by(Slot.start_time, Doctor.name)
        .limit(limit)
    )
    if department is not None:
        stmt = stmt.where(func.lower(Department.name) == department.lower())
    if day is not None:
        start = datetime.combine(day, time.min)
        stmt = stmt.where(Slot.start_time >= start, Slot.start_time < start + timedelta(days=1))
    return list(session.scalars(stmt))


def list_upcoming_appointments(
    session: Session,
    now: datetime | None = None,
    limit: int = 50,
    newest_first: bool = False,
) -> list[Appointment]:
    """Booked appointments that haven't started yet: soonest first, or most recently booked."""
    now = now or clinic_now()
    order = (
        (Appointment.created_at.desc(), Appointment.id.desc())
        if newest_first
        else (Slot.start_time,)
    )
    return list(
        session.scalars(
            select(Appointment)
            .join(Appointment.slot)
            .where(Appointment.status == AppointmentStatus.BOOKED, Slot.start_time > now)
            .order_by(*order)
            .limit(limit)
        )
    )


# --- session-bound facade ----------------------------------------------------


class ClinicRepository:
    """The repository functions bound to one session and one clock.

    This is what the dialogue manager depends on, so tests can hand it a seeded
    in-memory database and a pinned "now".
    """

    def __init__(self, session: Session, now: Callable[[], datetime] = clinic_now):
        self.session = session
        self.now = now

    def department_names(self) -> list[str]:
        return [d.name for d in list_departments(self.session)]

    def doctors_by_department(self, department: str | None = None) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for doctor in find_doctors(self.session, department):
            grouped.setdefault(doctor.department.name, []).append(doctor.name)
        return grouped

    def doctor_department(self, doctor: str) -> str | None:
        return self.session.scalar(
            select(Department.name)
            .join(Doctor.department)
            .where(func.lower(Doctor.name) == doctor.lower())
        )

    def find_free_slots(self, department, day, time_range=None, doctor=None, limit=3):
        return find_free_slots(
            self.session, department, day, time_range, doctor, limit, now=self.now()
        )

    def find_nearest_free_slots(self, department, around_datetime, limit=3, doctor=None):
        return find_nearest_free_slots(
            self.session, department, around_datetime, limit, now=self.now(), doctor=doctor
        )

    def book_slot(self, slot_id, name, phone):
        return book_slot(self.session, slot_id, name, phone, now=self.now())

    def get_appointment(self, ref=None, phone=None):
        return get_appointment(self.session, ref=ref, phone=phone, now=self.now())

    def cancel_appointment(self, ref):
        return cancel_appointment(self.session, ref)

    def reschedule_appointment(self, ref, new_slot_id):
        return reschedule_appointment(self.session, ref, new_slot_id, now=self.now())
