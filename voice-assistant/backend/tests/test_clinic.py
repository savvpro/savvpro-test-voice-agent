from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from threading import Barrier

import pytest

from app import config as C
from app.db import Database, SlotChanged
from app.dialogue import Brain, Call
from app.nlu import parse


TODAY = date(2026, 10, 26)
NOW = datetime(2026, 10, 26, 8, 0)
APPOINTMENT_DATE = "2026-10-27"


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "clinic.sqlite3"), now=lambda: NOW)
    yield database
    database.close()


def patient(guardian="Morgan Lee", child="Riley Lee", age=7, contact=None):
    return {"guardian_name": guardian, "child_name": child, "child_age": age, "contact": contact}


def test_generated_weekday_slots_are_exact_and_dynamic():
    slots = C.generate_slots()
    assert len(slots) == 35
    assert slots[0] == {"token": 1, "start_min": 540, "end_min": 554}
    assert all(right["start_min"] - left["start_min"] == 14 for left, right in zip(slots, slots[1:]))
    assert slots[-1] == {"token": 35, "start_min": 1016, "end_min": 1030}
    assert C.CLOSE_MIN == 17 * 60 + 10


@pytest.mark.parametrize("day", ["2026-10-31", "2026-11-01"])
def test_schedule_rejects_weekends(db, day):
    with pytest.raises(ValueError, match="Monday through Friday"):
        db.schedule(day)


def test_schedule_rejects_past_dates(db):
    with pytest.raises(ValueError, match="past date"):
        db.schedule("2026-10-23")


def test_schedule_returns_all_weekday_tokens_and_marks_occupancy(db):
    appointment = db.create_appointment(APPOINTMENT_DATE, patient())
    schedule = db.schedule(APPOINTMENT_DATE)
    assert len(schedule["slots"]) == 35
    assert schedule["slots"][0]["status"] == "occupied"
    assert schedule["slots"][0]["appointment"]["id"] == appointment["id"]
    assert schedule["active_count"] == 1
    assert schedule["available_count"] == 34


def test_capacity_is_35_and_a_cancelled_token_can_be_reused(db):
    appointments = [db.create_appointment(APPOINTMENT_DATE, patient(child=f"Child {index}"))
                    for index in range(C.DAILY_CAPACITY)]
    assert [appointment["token"] for appointment in appointments] == list(range(1, 36))
    assert db.create_appointment(APPOINTMENT_DATE, patient()) is None
    assert db.cancel_appointment(appointments[4]["id"])
    replacement = db.create_appointment(APPOINTMENT_DATE, patient(child="Replacement"))
    assert replacement["token"] == 5
    assert db.get_appointment(appointments[4]["id"])["status"] == "cancelled"
    assert db.appointment_history(appointments[4]["id"])[-1]["event"] == "cancelled"


def test_booking_requires_valid_child_and_guardian_details(db):
    with pytest.raises(ValueError, match="guardian name"):
        db.create_appointment(APPOINTMENT_DATE, {"child_name": "Riley", "child_age": 7})
    with pytest.raises(ValueError, match="between 0 and 18"):
        db.create_appointment(APPOINTMENT_DATE, patient(age=19))


def test_concurrent_connections_allocate_distinct_tokens(db, tmp_path):
    second = Database(str(tmp_path / "clinic.sqlite3"), now=lambda: NOW)
    barrier = Barrier(2)

    def reserve(database, child):
        barrier.wait()
        return database.create_appointment(APPOINTMENT_DATE, patient(child=child))

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda pair: reserve(*pair), [(db, "One"), (second, "Two")]))
        assert sorted(result["token"] for result in results) == [1, 2]
    finally:
        second.close()


def test_stale_concurrent_token_offer_is_rejected(db, tmp_path):
    second = Database(str(tmp_path / "clinic.sqlite3"), now=lambda: NOW)
    try:
        first_offer = db.preview(APPOINTMENT_DATE)
        second_offer = second.preview(APPOINTMENT_DATE)
        assert first_offer["token"] == second_offer["token"] == 1
        db.create_appointment(APPOINTMENT_DATE, patient(child="First"), expected_token=1)
        with pytest.raises(SlotChanged) as error:
            second.create_appointment(APPOINTMENT_DATE, patient(child="Second"), expected_token=1)
        assert error.value.token == 2
        assert len(db.list_appointments()) == 1
    finally:
        second.close()


def test_reschedule_keeps_history_and_releases_old_slot(db):
    original = db.create_appointment(APPOINTMENT_DATE, patient())
    moved = db.reschedule_appointment(original["id"], "2026-10-28", expected_token=1)
    assert moved["token"] == 1
    assert moved["appointment_date"] == "2026-10-28"
    assert moved["previous_appointment_id"] == original["id"]
    assert db.get_appointment(original["id"])["status"] == "rescheduled"
    assert db.preview(APPOINTMENT_DATE)["token"] == 1
    assert db.appointment_history(original["id"])[-1]["event"] == "rescheduled_from"


def test_nlu_extracts_clinic_details_and_rejects_bad_dates():
    parsed = parse("book appointment parent name is Alice child name is Sam age 5 tomorrow", TODAY)
    assert parsed.intent == "BOOK"
    assert parsed.guardian_name == "Alice"
    assert parsed.child_name == "Sam"
    assert parsed.child_age == 5
    assert parsed.date == date(2026, 10, 27)
    invalid = parse("book appointment for February 30", TODAY)
    assert invalid.date_error == "invalid_date"
    verified_by_phone = parse("check token 3 on 2026-10-27 contact 5551234567", TODAY)
    assert verified_by_phone.contact == "5551234567"


def test_dialogue_confirms_before_committing_appointment(db):
    brain, call = Brain(db, now=lambda: NOW), Call("booking-test")
    brain.start(call)
    offered = brain.handle(call, "book appointment parent name is Alice child name is Sam age 5 tomorrow")
    assert offered.state == "CONFIRM_BOOK"
    assert offered.slots["token"] == 1
    assert "Token Number 1" in offered.reply and "9:00 AM" in offered.reply
    assert db.list_appointments() == []
    confirmed = brain.handle(call, "yes")
    assert confirmed.action == "BOOKED:1"
    assert confirmed.appointment["status"] == "active"
    assert db.list_appointments()[0]["child_name"] == "Sam"


def test_dialogue_check_cancel_and_reschedule(db):
    appointment = db.create_appointment(APPOINTMENT_DATE, patient())
    brain = Brain(db, now=lambda: NOW)

    check_call = Call("check-test")
    brain.start(check_call)
    found = brain.handle(check_call, f"check appointment token {appointment['token']} on {APPOINTMENT_DATE} guardian name Morgan Lee")
    assert found.action == "APPOINTMENT_FOUND"
    assert "Status: active" in found.reply

    cancel_call = Call("cancel-test")
    brain.start(cancel_call)
    ask_cancel = brain.handle(cancel_call, f"cancel appointment token {appointment['token']} on {APPOINTMENT_DATE} guardian name Morgan Lee")
    assert ask_cancel.state == "CONFIRM_CANCEL"
    assert db.get_appointment(appointment["id"])["status"] == "active"
    cancelled = brain.handle(cancel_call, "yes")
    assert cancelled.action == "CANCELLED:1"
    assert db.get_appointment(appointment["id"])["status"] == "cancelled"

    new_appointment = db.create_appointment(APPOINTMENT_DATE, patient(child="Jordan"))
    reschedule_call = Call("reschedule-test")
    brain.start(reschedule_call)
    offer = brain.handle(reschedule_call, f"reschedule appointment token {new_appointment['token']} on {APPOINTMENT_DATE} guardian name Morgan Lee")
    assert offer.state == "COLLECT_RESCHEDULE"
    offered = brain.handle(reschedule_call, "Wednesday")
    assert offered.state == "CONFIRM_RESCHEDULE"
    moved = brain.handle(reschedule_call, "yes")
    assert moved.action == "RESCHEDULED:1"
    assert db.get_appointment(new_appointment["id"])["status"] == "rescheduled"
    assert moved.appointment["appointment_date"] == "2026-10-28"


def test_dialogue_rejects_weekend_and_corrects_invalid_date(db):
    brain, call = Brain(db, now=lambda: NOW), Call("invalid-test")
    brain.start(call)
    result = brain.handle(call, "book appointment parent name is Alice child name is Sam age 5 Saturday")
    assert result.action == "REJECT:closed_day"
    assert result.state == "COLLECT_BOOK"
    corrected = brain.handle(call, "Wednesday")
    assert corrected.state == "CONFIRM_BOOK"
    assert corrected.slots["date"] == "2026-10-28"


def test_dialogue_reprompts_for_invalid_age_then_accepts_correction(db):
    brain, call = Brain(db, now=lambda: NOW), Call("age-correction-test")
    brain.start(call)
    first = brain.handle(call, "book appointment parent name Alice child name Riley")
    assert first.expecting == "child_age"
    rejected = brain.handle(call, "19")
    assert rejected.expecting == "child_age"
    corrected = brain.handle(call, "5")
    assert corrected.expecting == "date"
    assert corrected.slots["child_age"] == 5


def test_dialogue_reports_full_day_unavailable(db):
    for index in range(C.DAILY_CAPACITY):
        db.create_appointment(APPOINTMENT_DATE, patient(child=f"Child {index}"))
    brain, call = Brain(db, now=lambda: NOW), Call("full-day-test")
    brain.start(call)
    response = brain.handle(call, "book appointment parent name is Alice child name is Sam age 5 tomorrow")
    assert response.action == "UNAVAILABLE"
    assert "All 35 appointment tokens are booked" in response.reply
