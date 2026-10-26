"""End-to-end happy paths: text in, NLU, dialogue manager, real (in-memory) DB."""

from datetime import date, datetime

from sqlalchemy import select

from app.db.models import Appointment, AppointmentStatus
from app.db.repository import get_appointment
from app.dialogue.states import State

NEXT_MONDAY = date(2030, 1, 14)


def appointments(session):
    return session.scalars(select(Appointment)).all()


def book_existing(c, department="Cardiology", day=date(2030, 1, 10), phone="03001112222"):
    """An appointment made earlier, for reschedule/cancel tests."""
    slot = c.repo.find_free_slots(department, day, limit=1)[0]
    return c.repo.book_slot(slot.id, "Omar Farooq", phone)


def test_book_in_one_sentence(call, clinic):
    c = call()
    assert c.last.state == State.IDENTIFY_TASK

    d = c.say("Book me with a dermatologist next Monday at 10 am")
    assert d.frame.department == "Dermatology"
    assert d.frame.chosen_slot.start == datetime(2030, 1, 14, 10, 0)
    assert d.expected_slot == "patient_name"

    c.say("Ali Raza")
    d = c.say("0300 1234567")
    assert d.state == State.CONFIRM

    d = c.say("yes")
    assert (d.state, d.action) == (State.DONE, "booked")
    booked = get_appointment(clinic, ref=d.frame.booking_ref)
    assert booked.patient.name == "Ali Raza"
    assert booked.patient.phone == "03001234567"
    assert booked.slot.start_time == datetime(2030, 1, 14, 10, 0)
    assert booked.slot.doctor.department.name == "Dermatology"
    assert booked.slot.is_booked
    assert d.frame.booking_ref in d.reply_text

    d = c.say("no thanks")
    assert (d.state, d.action, d.end_call) == (State.END, "ended", True)


def test_book_step_by_step(call, clinic):
    c = call()
    d = c.say("I want to book an appointment")
    assert d.expected_slot == "department"
    d = c.say("ENT please")
    assert d.expected_slot == "date"
    d = c.say("Wednesday")
    assert d.state == State.OFFER_SLOTS
    assert len(d.frame.candidate_slots) == 3
    assert all(o.department == "ENT" for o in d.frame.candidate_slots)

    d = c.say("the first one")
    first = c.decisions[-2].frame.candidate_slots[0]
    assert d.frame.chosen_slot == first
    c.say("my name is Hamza Yousaf")
    c.say("zero three zero zero five five five one two three four")
    d = c.say("yes please")
    assert d.action == "booked"
    [booked] = appointments(clinic)
    assert booked.slot_id == first.slot_id
    assert booked.patient.phone == "03005551234"


def test_check_availability_then_book(call, clinic):
    c = call()
    d = c.say("does cardiology have anything thursday")
    assert d.state == State.OFFER_SLOTS
    assert all(o.start.date() == date(2030, 1, 10) for o in d.frame.candidate_slots)
    c.say("the second one")
    c.say("Sana Malik")
    c.say("03215551234")
    assert c.say("yes").action == "booked"


def test_book_with_named_doctor(call, clinic):
    c = call()
    d = c.say("I want an appointment with Dr Saima tomorrow at 11")
    assert d.frame.department == "Cardiology"
    assert d.frame.chosen_slot.doctor == "Dr. Saima Rauf"
    assert d.frame.chosen_slot.start == datetime(2030, 1, 8, 11, 0)


def test_reschedule_by_reference(call, clinic):
    c = call()
    existing = book_existing(c)
    old_slot = existing.slot_id

    d = c.say(f"I need to reschedule my appointment, reference {existing.booking_ref}")
    assert d.frame.appointment.booking_ref == existing.booking_ref
    assert d.expected_slot == "date"

    d = c.say("next Monday")
    assert d.state == State.OFFER_SLOTS
    assert all(o.doctor == existing.slot.doctor.name for o in d.frame.candidate_slots)
    c.say("the first one")
    d = c.say("yes")
    assert (d.state, d.action) == (State.DONE, "rescheduled")

    moved = get_appointment(clinic, ref=existing.booking_ref)
    assert moved.slot_id != old_slot
    assert moved.slot.start_time.date() == NEXT_MONDAY
    assert moved.status == AppointmentStatus.BOOKED


def test_reschedule_by_phone_with_new_date_up_front(call, clinic):
    c = call()
    existing = book_existing(c, phone="03004445555")
    c.say("can I move my booking to Friday")
    d = c.say("my number is 0300 4445555")
    assert d.frame.appointment.booking_ref == existing.booking_ref
    assert d.state == State.OFFER_SLOTS
    assert d.frame.candidate_slots[0].start.date() == date(2030, 1, 11)


def test_cancel_by_reference(call, clinic):
    c = call()
    existing = book_existing(c)
    d = c.say("I want to cancel my appointment")
    assert d.expected_slot == "booking_ref"
    d = c.say(existing.booking_ref)
    assert d.state == State.CONFIRM
    d = c.say("yes")
    assert (d.state, d.action) == (State.DONE, "cancelled")
    assert get_appointment(clinic, ref=existing.booking_ref).status == AppointmentStatus.CANCELLED


def test_cancel_declined_keeps_appointment(call, clinic):
    c = call()
    existing = book_existing(c)
    c.say(f"cancel booking {existing.booking_ref}")
    d = c.say("no")
    assert d.action == "cancel_declined"
    assert get_appointment(clinic, ref=existing.booking_ref).status == AppointmentStatus.BOOKED


def test_clinic_info_without_a_task(call):
    c = call()
    assert "9 AM to 5 PM" in c.say("what are your opening hours").reply_text
    assert "Jasmine Road" in c.say("where is the clinic").reply_text
    assert "Cardiology" in c.say("which departments do you have").reply_text
    d = c.say("who are the doctors in ENT")
    assert "Dr. Zain Abbas" in d.reply_text and "Dr. Mehwish Khalid" in d.reply_text
    assert d.state == State.IDENTIFY_TASK


def test_clinic_info_mid_booking_returns_to_the_question(call):
    c = call()
    question = c.say("I'd like to book with the cardiologist").reply_text
    d = c.say("what time do you close on saturday")
    assert d.reply_text.endswith(question)
    assert d.frame.date is None  # the date in the question is not booked
    assert d.expected_slot == "date"


def test_second_booking_in_the_same_call_starts_fresh(call, clinic):
    c = call()
    c.say("Book me with a dermatologist next Monday at 10 am")
    c.say("Ali Raza")
    c.say("03001234567")
    c.say("yes")
    d = c.say("I also want to book for my son with the pediatrician")
    assert d.frame.department == "Pediatrics"
    assert d.frame.patient_name is None
    assert d.frame.date is None
