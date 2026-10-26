import re
from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import repository as repo
from app.db.base import Base
from app.db.models import Appointment, AppointmentStatus, Patient, Slot
from app.db.seed import seed_database
from app.db.session import create_db_engine
from tests.conftest import NOW, REF_MONDAY

REF_PATTERN = re.compile(r"^SC-[A-HJ-NP-Z2-9]{4}$")
TUESDAY = REF_MONDAY + timedelta(days=1)
SUNDAY = REF_MONDAY + timedelta(days=6)


def first_free_slot(session, department="Cardiology", day=TUESDAY):
    return repo.find_free_slots(session, department, day, limit=1, now=NOW)[0]


def book(session, slot, name="Test Caller", phone="03001234567"):
    return repo.book_slot(session, slot.id, name, phone, now=NOW)


# --- departments & doctors -------------------------------------------------


def test_list_departments_sorted(seeded):
    names = [d.name for d in repo.list_departments(seeded)]
    assert names == sorted(names)
    assert len(names) == 7
    assert "Cardiology" in names


def test_find_doctors_by_department_is_case_insensitive(seeded):
    doctors = repo.find_doctors(seeded, "cardiology")
    assert len(doctors) == 2
    assert all(d.department.name == "Cardiology" for d in doctors)


def test_find_doctors_unknown_department_returns_empty(seeded):
    assert repo.find_doctors(seeded, "Dentistry") == []


def test_find_doctors_without_department_returns_all(seeded):
    assert len(repo.find_doctors(seeded)) == 14


# --- free slots ------------------------------------------------------------


def test_find_free_slots_returns_earliest_in_department(seeded):
    slots = repo.find_free_slots(seeded, "Dermatology", TUESDAY, now=NOW)
    assert len(slots) == 3
    starts = [s.start_time for s in slots]
    assert starts == sorted(starts)
    assert starts[0] == datetime.combine(TUESDAY, time(9))
    assert all(s.doctor.department.name == "Dermatology" for s in slots)
    assert all(not s.is_booked for s in slots)


def test_find_free_slots_respects_time_range(seeded):
    slots = repo.find_free_slots(
        seeded, "ENT", TUESDAY, time_range=(time(14), time(17)), limit=50, now=NOW
    )
    assert slots
    assert all(time(14) <= s.start_time.time() < time(17) for s in slots)


def test_find_free_slots_filters_by_doctor(seeded):
    doctor = repo.find_doctors(seeded, "Pediatrics")[1]
    slots = repo.find_free_slots(seeded, "Pediatrics", TUESDAY, doctor=doctor.name.upper(), now=NOW)
    assert slots
    assert all(s.doctor_id == doctor.id for s in slots)


def test_find_free_slots_on_sunday_is_empty(seeded):
    assert repo.find_free_slots(seeded, "Cardiology", SUNDAY, now=NOW) == []


def test_find_free_slots_excludes_past_slots(seeded):
    now = datetime.combine(REF_MONDAY, time(10, 5))
    slots = repo.find_free_slots(seeded, "Cardiology", REF_MONDAY, limit=50, now=now)
    assert slots
    assert all(s.start_time > now for s in slots)


def test_find_free_slots_excludes_booked_slots(seeded):
    slot = first_free_slot(seeded)
    book(seeded, slot)
    slots = repo.find_free_slots(seeded, "Cardiology", TUESDAY, limit=100, now=NOW)
    assert slot.id not in {s.id for s in slots}


def test_find_nearest_free_slots_around_lunch(seeded):
    # 13:30 Monday is inside the lunch break: 14:00 (30 min away) beats 12:40 (50 min).
    around = datetime.combine(REF_MONDAY, time(13, 30))
    slots = repo.find_nearest_free_slots(seeded, "Cardiology", around, now=NOW)
    starts = [s.start_time.time() for s in slots]
    assert starts == [time(14), time(14), time(12, 40)]


def test_find_nearest_free_slots_skips_taken_slot(seeded):
    around = datetime.combine(TUESDAY, time(10))
    taken = repo.find_free_slots(
        seeded, "ENT", TUESDAY, time_range=(time(10), time(10, 20)), limit=5, now=NOW
    )
    for slot in taken:
        book(seeded, slot, phone=f"0300555{slot.id:04d}")
    slots = repo.find_nearest_free_slots(seeded, "ENT", around, now=NOW)
    assert len(slots) == 3
    assert all(s.start_time != around for s in slots)
    assert {s.start_time.time() for s in slots} <= {time(9, 40), time(10, 20)}


def test_find_nearest_free_slots_prefers_requested_doctor(seeded):
    around = datetime.combine(TUESDAY, time(10))
    slots = repo.find_nearest_free_slots(
        seeded, "ENT", around, now=NOW, doctor="Dr. Mehwish Khalid"
    )
    assert len(slots) == 3
    assert {s.doctor.name for s in slots} == {"Dr. Mehwish Khalid"}
    # Without a preference, the other doctor's 10:00 slot is just as near.
    anyone = repo.find_nearest_free_slots(seeded, "ENT", around, now=NOW)
    assert {s.doctor.name for s in anyone} == {"Dr. Mehwish Khalid", "Dr. Zain Abbas"}


def test_find_nearest_free_slots_falls_back_to_other_doctors(seeded):
    # Dr. Khalid has a single free slot left, days later: it comes first, then
    # the nearest slots of the other ENT doctor fill the remaining places.
    around = datetime.combine(TUESDAY, time(10))
    khalid = [
        s
        for s in seeded.scalars(select(Slot).where(Slot.is_booked.is_(False))).all()
        if s.doctor.name == "Dr. Mehwish Khalid"
    ]
    left = max(khalid, key=lambda s: s.start_time)
    assert left.start_time.date() > TUESDAY + timedelta(days=2)
    for slot in khalid:
        slot.is_booked = slot is not left
    seeded.flush()
    slots = repo.find_nearest_free_slots(
        seeded, "ENT", around, now=NOW, doctor="Dr. Mehwish Khalid"
    )
    assert slots[0].id == left.id
    assert [s.doctor.name for s in slots[1:]] == ["Dr. Zain Abbas", "Dr. Zain Abbas"]
    assert all(abs(s.start_time - around) < timedelta(days=1) for s in slots[1:])


def test_find_nearest_free_slots_never_returns_past(seeded):
    now = datetime.combine(TUESDAY, time(12))
    around = datetime.combine(TUESDAY, time(9))
    slots = repo.find_nearest_free_slots(seeded, "Cardiology", around, now=now)
    assert slots
    assert all(s.start_time > now for s in slots)


# --- booking ---------------------------------------------------------------


def test_book_slot_creates_appointment(seeded):
    slot = first_free_slot(seeded)
    appointment = book(seeded, slot, name="Test Caller", phone="03001234567")

    assert REF_PATTERN.match(appointment.booking_ref)
    assert appointment.status == AppointmentStatus.BOOKED
    assert appointment.patient.name == "Test Caller"
    assert appointment.patient.phone == "03001234567"
    assert seeded.get(Slot, slot.id).is_booked is True


def test_double_booking_same_slot_is_rejected(seeded):
    slot = first_free_slot(seeded)
    first = book(seeded, slot, name="First Caller", phone="03001111111")

    with pytest.raises(repo.SlotUnavailableError):
        book(seeded, slot, name="Second Caller", phone="03002222222")

    appointments = seeded.scalars(select(Appointment).where(Appointment.slot_id == slot.id)).all()
    assert [a.id for a in appointments] == [first.id]
    assert seeded.scalar(select(Patient).where(Patient.phone == "03002222222")) is None


def test_double_booking_from_two_sessions_is_rejected(tmp_path):
    # Two independent connections to the same file DB, both seeing the slot as free.
    engine = create_db_engine(f"sqlite:///{tmp_path / 'clinic.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as setup:
        seed_database(setup, start=REF_MONDAY, days=2, prebook_ratio=0.0)

    with (
        Session(engine, expire_on_commit=False) as a,
        Session(engine, expire_on_commit=False) as b,
    ):
        slot_a = first_free_slot(a)
        slot_b = b.get(Slot, slot_a.id)
        assert slot_a.is_booked is False and slot_b.is_booked is False

        repo.book_slot(a, slot_a.id, "Caller A", "03001111111", now=NOW)
        with pytest.raises(repo.SlotUnavailableError):
            repo.book_slot(b, slot_b.id, "Caller B", "03002222222", now=NOW)

    with Session(engine) as check:
        count = check.scalar(
            select(func.count()).select_from(Appointment).where(Appointment.slot_id == slot_a.id)
        )
        assert count == 1
    engine.dispose()


def test_database_rejects_two_active_appointments_on_one_slot(seeded):
    slot = first_free_slot(seeded)
    patient = Patient(name="Someone", phone="03009999999")
    seeded.add_all(
        [
            Appointment(booking_ref="SC-AAAA", patient=patient, slot_id=slot.id),
            Appointment(booking_ref="SC-BBBB", patient=patient, slot_id=slot.id),
        ]
    )
    with pytest.raises(IntegrityError):
        seeded.commit()


def test_book_past_slot_is_rejected(seeded):
    slot = first_free_slot(seeded, day=REF_MONDAY)  # 09:00 Monday
    later = datetime.combine(REF_MONDAY, time(12))
    with pytest.raises(repo.SlotUnavailableError):
        repo.book_slot(seeded, slot.id, "Late Caller", "03003333333", now=later)
    assert seeded.get(Slot, slot.id).is_booked is False


def test_book_unknown_slot_is_rejected(seeded):
    with pytest.raises(repo.SlotUnavailableError):
        repo.book_slot(seeded, 999_999, "Nobody", "03004444444", now=NOW)


def test_same_phone_reuses_patient(seeded):
    slots = repo.find_free_slots(seeded, "ENT", TUESDAY, limit=2, now=NOW)
    a = book(seeded, slots[0], name="Sam", phone="03005555555")
    b = book(seeded, slots[1], name="Sam Khan", phone="03005555555")
    assert a.patient_id == b.patient_id
    assert b.patient.name == "Sam Khan"
    assert a.booking_ref != b.booking_ref


# --- lookup ----------------------------------------------------------------


def test_get_appointment_by_ref_is_case_insensitive(seeded):
    appointment = book(seeded, first_free_slot(seeded))
    found = repo.get_appointment(seeded, ref=f"  {appointment.booking_ref.lower()} ")
    assert found is not None and found.id == appointment.id


def test_get_appointment_by_phone_returns_soonest_upcoming(seeded):
    # Slots 0 and 1 are both 09:00 (two ENT doctors); slot 2 is 09:20.
    slots = repo.find_free_slots(seeded, "ENT", TUESDAY, limit=3, now=NOW)
    sooner_slot, later_slot = slots[0], slots[2]
    assert sooner_slot.start_time < later_slot.start_time
    later = book(seeded, later_slot, phone="03006666666")
    sooner = book(seeded, sooner_slot, phone="03006666666")
    found = repo.get_appointment(seeded, phone="03006666666", now=NOW)
    assert found.id == sooner.id
    assert later.id != sooner.id


def test_get_appointment_not_found(seeded):
    assert repo.get_appointment(seeded, ref="SC-ZZZZ") is None
    assert repo.get_appointment(seeded, phone="03000000000", now=NOW) is None


def test_get_appointment_requires_ref_or_phone(seeded):
    with pytest.raises(ValueError):
        repo.get_appointment(seeded)


# --- cancel ----------------------------------------------------------------


def test_cancel_frees_slot_and_slot_can_be_rebooked(seeded):
    slot = first_free_slot(seeded)
    appointment = book(seeded, slot)

    cancelled = repo.cancel_appointment(seeded, appointment.booking_ref)
    assert cancelled.status == AppointmentStatus.CANCELLED
    assert seeded.get(Slot, slot.id).is_booked is False
    assert repo.get_appointment(seeded, phone="03001234567", now=NOW) is None

    rebooked = book(seeded, slot, name="Next Caller", phone="03007777777")
    assert rebooked.status == AppointmentStatus.BOOKED


def test_cancel_twice_raises(seeded):
    appointment = book(seeded, first_free_slot(seeded))
    repo.cancel_appointment(seeded, appointment.booking_ref)
    with pytest.raises(repo.AppointmentNotFoundError):
        repo.cancel_appointment(seeded, appointment.booking_ref)


def test_cancel_unknown_ref_raises(seeded):
    with pytest.raises(repo.AppointmentNotFoundError):
        repo.cancel_appointment(seeded, "SC-ZZZZ")


# --- reschedule ------------------------------------------------------------


def test_reschedule_moves_appointment_and_frees_old_slot(seeded):
    old_slot, new_slot = repo.find_free_slots(seeded, "Cardiology", TUESDAY, limit=3, now=NOW)[::2]
    appointment = book(seeded, old_slot)

    moved = repo.reschedule_appointment(seeded, appointment.booking_ref, new_slot.id, now=NOW)

    assert moved.booking_ref == appointment.booking_ref
    assert moved.slot_id == new_slot.id
    assert moved.status == AppointmentStatus.BOOKED
    assert seeded.get(Slot, old_slot.id).is_booked is False
    assert seeded.get(Slot, new_slot.id).is_booked is True


def test_reschedule_to_taken_slot_leaves_appointment_unchanged(seeded):
    mine, theirs = repo.find_free_slots(seeded, "Cardiology", TUESDAY, limit=2, now=NOW)
    appointment = book(seeded, mine, phone="03001111111")
    book(seeded, theirs, phone="03002222222")

    with pytest.raises(repo.SlotUnavailableError):
        repo.reschedule_appointment(seeded, appointment.booking_ref, theirs.id, now=NOW)

    seeded.expire_all()
    unchanged = repo.get_appointment(seeded, ref=appointment.booking_ref)
    assert unchanged.slot_id == mine.id
    assert seeded.get(Slot, mine.id).is_booked is True


def test_reschedule_cancelled_appointment_raises(seeded):
    slots = repo.find_free_slots(seeded, "Cardiology", TUESDAY, limit=2, now=NOW)
    appointment = book(seeded, slots[0])
    repo.cancel_appointment(seeded, appointment.booking_ref)
    with pytest.raises(repo.AppointmentNotFoundError):
        repo.reschedule_appointment(seeded, appointment.booking_ref, slots[1].id, now=NOW)


# --- helpers ---------------------------------------------------------------


def test_generate_booking_ref_format():
    for _ in range(200):
        assert REF_PATTERN.match(repo.generate_booking_ref())


def test_clinic_now_is_naive():
    assert repo.clinic_now().tzinfo is None


# --- admin views -------------------------------------------------------------


def test_list_slots_for_department_and_day(seeded):
    slots = repo.list_slots(seeded, department="ent", day=TUESDAY)
    assert slots
    assert {s.doctor.department.name for s in slots} == {"ENT"}
    assert {s.start_time.date() for s in slots} == {TUESDAY}
    assert [s.start_time for s in slots] == sorted(s.start_time for s in slots)


def test_list_slots_shows_booked_ones(seeded):
    slot = first_free_slot(seeded)
    book(seeded, slot)
    listed = {s.id: s.is_booked for s in repo.list_slots(seeded, "Cardiology", TUESDAY)}
    assert listed[slot.id] is True


def test_list_upcoming_appointments_skips_past_and_cancelled(seeded):
    early = first_free_slot(seeded, day=REF_MONDAY)
    kept = book(seeded, first_free_slot(seeded, "ENT"), phone="03001111111")
    gone = book(seeded, first_free_slot(seeded, "Dermatology"), phone="03002222222")
    book(seeded, early, phone="03003333333")
    repo.cancel_appointment(seeded, gone.booking_ref)
    after_early = early.start_time + timedelta(minutes=1)
    refs = [a.booking_ref for a in repo.list_upcoming_appointments(seeded, now=after_early)]
    assert refs == [kept.booking_ref]


def test_list_upcoming_appointments_newest_first(seeded):
    # booked first but sooner, then booked later for a later day
    sooner = book(seeded, first_free_slot(seeded, "ENT", day=TUESDAY))
    later_day = first_free_slot(seeded, "ENT", day=TUESDAY + timedelta(days=2))
    latest = repo.book_slot(
        seeded, later_day.id, "B", "03004444444", now=NOW + timedelta(minutes=5)
    )
    soonest = repo.list_upcoming_appointments(seeded, now=NOW)
    assert [a.booking_ref for a in soonest] == [sooner.booking_ref, latest.booking_ref]
    newest = repo.list_upcoming_appointments(seeded, now=NOW, newest_first=True)
    assert [a.booking_ref for a in newest] == [latest.booking_ref, sooner.booking_ref]
