"""Messy callers: one test (or more) per case in PLAN.md section 2.

Every conversation runs text -> NLU -> DialogueManager against a seeded
in-memory database, and asserts on the final state, the action and the DB.
Call time is Monday 7 January 2030, 08:00, unless a test says otherwise.
"""

from datetime import date, datetime, time

import pytest
from sqlalchemy import func, select

from app.db.models import Appointment, AppointmentStatus
from app.db.repository import get_appointment
from app.dialogue.states import State

FRIDAY = date(2030, 1, 11)
NEXT_MONDAY = date(2030, 1, 14)


def appointment_count(session) -> int:
    return session.scalar(select(func.count()).select_from(Appointment))


def finish_booking(c, name="Ali Raza", phone="03001234567"):
    c.say(name)
    c.say(phone)
    return c.say("yes")


def take_slots(c, department, day, at, doctors=2):
    """Book every doctor's slot at day/at so the caller can't have it."""
    window = (at, (datetime.combine(day, at).replace(minute=at.minute + 1)).time())
    for i, slot in enumerate(c.repo.find_free_slots(department, day, window, limit=doctors)):
        c.repo.book_slot(slot.id, "Someone Else", f"0300555{i:04d}")


# --- changes a slot mid-flow ----------------------------------------------


def test_changes_date_mid_flow(call, clinic):
    c = call()
    c.say("Book me with a dermatologist next Monday at 10 am")
    d = c.say("actually make it Friday")
    assert "changed the date to Friday 11 January" in d.reply_text or (
        "date changed to Friday 11 January" in d.reply_text
    )
    assert d.frame.chosen_slot.start == datetime(2030, 1, 11, 10, 0)
    assert finish_booking(c).action == "booked"
    [booked] = clinic.scalars(select(Appointment)).all()
    assert booked.slot.start_time == datetime(2030, 1, 11, 10, 0)


def test_changes_time_mid_flow(call, clinic):
    c = call()
    c.say("I need a cardiologist on Friday at 11")
    d = c.say("no wait, 4pm instead")
    assert "4 PM" in d.reply_text
    assert d.frame.chosen_slot.start == datetime(2030, 1, 11, 16, 0)


def test_changes_department_after_slot_was_offered(call):
    c = call()
    c.say("I want to see a skin doctor tomorrow")
    d = c.say("oh sorry, I meant cardiology not dermatology")
    assert d.frame.department == "Cardiology"
    assert d.state == State.OFFER_SLOTS
    assert all(o.department == "Cardiology" for o in d.frame.candidate_slots)


def test_changes_details_at_confirmation(call, clinic):
    c = call()
    c.say("Book me with a dermatologist next Monday at 10 am")
    c.say("Ali Raza")
    c.say("03001234567")
    d = c.say("actually make it 11")
    assert d.state == State.CONFIRM
    assert d.frame.chosen_slot.start == datetime(2030, 1, 14, 11, 0)
    assert c.say("yes").action == "booked"


# --- several slots at once --------------------------------------------------


def test_several_slots_in_one_sentence(call):
    c = call()
    d = c.say("Book me with a dermatologist next Monday at 10 am")
    assert d.frame.department == "Dermatology"
    assert d.frame.date == NEXT_MONDAY
    assert d.frame.time == time(10)
    assert d.expected_slot == "patient_name"  # straight to the caller's details


def test_name_and_phone_in_one_sentence(call):
    c = call()
    c.say("Book me with a dermatologist next Monday at 10 am")
    d = c.say("my name is Omar Farooq and my number is 03015550123")
    assert d.state == State.CONFIRM
    assert (d.frame.patient_name, d.frame.phone) == ("Omar Farooq", "03015550123")


# --- requested slot taken -> 3 nearest -------------------------------------


def test_taken_slot_offers_three_nearest(call, clinic):
    c = call()
    take_slots(c, "Dermatology", NEXT_MONDAY, time(10))
    d = c.say("Book me with a dermatologist next Monday at 10 am")
    assert d.state == State.OFFER_SLOTS
    starts = [o.start for o in d.frame.candidate_slots]
    assert len(starts) == 3
    assert datetime(2030, 1, 14, 10, 0) not in starts
    assert all(abs(s - datetime(2030, 1, 14, 10, 0)).total_seconds() <= 20 * 60 for s in starts)


def test_taken_slot_offers_requested_doctor_first(call):
    c = call()
    take_slots(c, "Cardiology", FRIDAY, time(11))
    d = c.say("I'd like to see Dr Saima Rauf on Friday at 11")
    assert d.state == State.OFFER_SLOTS
    assert [o.doctor for o in d.frame.candidate_slots] == ["Dr. Saima Rauf"] * 3
    assert datetime(2030, 1, 11, 11, 0) not in {o.start for o in d.frame.candidate_slots}


def test_pick_offered_slot_by_ordinal(call, clinic):
    c = call()
    take_slots(c, "Dermatology", NEXT_MONDAY, time(10))
    offered = c.say("Book me with a dermatologist next Monday at 10 am").frame.candidate_slots
    d = c.say("the second")
    assert d.frame.chosen_slot == offered[1]
    d = finish_booking(c)
    assert d.action == "booked"
    assert get_appointment(clinic, ref=d.frame.booking_ref).slot_id == offered[1].slot_id


def test_pick_offered_slot_by_time(call):
    c = call()
    take_slots(c, "Dermatology", NEXT_MONDAY, time(10))
    offered = c.say("Book me with a dermatologist next Monday at 10 am").frame.candidate_slots
    later = next(o for o in offered if o.start.time() == time(10, 20))
    d = c.say("10:20 please")
    assert d.frame.chosen_slot == later


def test_the_2nd_means_option_two_not_a_date(call):
    c = call()
    offered = c.say("cardiology on Friday").frame.candidate_slots
    d = c.say("the 2nd")
    assert d.frame.chosen_slot == offered[1]
    assert d.frame.date == FRIDAY


def test_yes_to_several_offers_asks_which(call):
    c = call()
    c.say("cardiology on Friday")
    d = c.say("yes")
    assert d.state == State.OFFER_SLOTS
    assert "first" in d.reply_text and "second" in d.reply_text


def test_rejects_all_offers(call):
    c = call()
    c.say("cardiology on Friday")
    d = c.say("no")
    assert d.state == State.COLLECT_SLOTS
    assert d.expected_slot == "date"
    assert d.frame.date is None and not d.frame.candidate_slots


# --- dates and times outside the rules --------------------------------------


@pytest.mark.parametrize(
    ("utterance", "reply_contains"),
    [
        ("cardiology on 5/1/2030", "already passed"),  # past date
        ("cardiology on sunday", "closed on Sunday"),
        ("cardiology on the 20th of february", "30 days"),  # too far
    ],
)
def test_invalid_dates_are_rejected(call, clinic, utterance, reply_contains):
    c = call()
    d = c.say(utterance)
    assert reply_contains in d.reply_text
    assert d.frame.date is None
    assert d.expected_slot == "date"
    assert appointment_count(clinic) == 0


@pytest.mark.parametrize(
    ("utterance", "reply_contains"),
    [
        ("cardiology on friday at 8 am", "too early"),
        ("cardiology on friday at 7 pm", "after closing"),
        ("cardiology on friday at half past one", "lunch"),
        ("cardiology on saturday at 3 pm", "close at 1 PM"),
    ],
)
def test_times_outside_opening_hours_are_rejected(call, utterance, reply_contains):
    c = call()
    d = c.say(utterance)
    assert reply_contains in d.reply_text
    assert d.frame.time is None
    assert d.expected_slot == "time"


def test_time_already_passed_today(call):
    c = call(now=datetime(2030, 1, 7, 11, 0))
    d = c.say("cardiology today at 10 am")
    assert "already passed" in d.reply_text
    assert d.expected_slot == "time"


def test_recovers_after_invalid_date(call):
    c = call()
    c.say("cardiology on sunday")
    d = c.say("monday then")
    assert d.state == State.OFFER_SLOTS
    assert d.frame.date == NEXT_MONDAY


# --- vague times ------------------------------------------------------------


@pytest.mark.parametrize(
    ("utterance", "start", "end"),
    [
        ("ENT on friday morning", time(9), time(13)),
        ("ENT on friday afternoon", time(14), time(17)),
        ("ENT on friday after lunch", time(14), time(17)),
    ],
)
def test_vague_time_offers_slots_in_that_range(call, utterance, start, end):
    c = call()
    d = c.say(utterance)
    assert d.state == State.OFFER_SLOTS
    assert all(start <= o.start.time() < end for o in d.frame.candidate_slots)


def test_vague_time_when_that_part_of_day_is_full(call, clinic):
    c = call()
    morning = c.repo.find_free_slots("ENT", FRIDAY, (time(9), time(13)), limit=100)
    for i, slot in enumerate(morning):
        c.repo.book_slot(slot.id, "Someone Else", f"0300555{i:04d}")
    d = c.say("ENT on friday morning")
    assert "nothing free" in d.reply_text.lower() or "fully booked" in d.reply_text
    assert d.state == State.OFFER_SLOTS
    assert len(d.frame.candidate_slots) == 3


# --- ambiguous date -----------------------------------------------------------


def test_the_5th_is_the_next_upcoming_5th(call):
    c = call()  # 7 January: the 5th has passed this month
    d = c.say("cardiology on the 5th")
    assert d.frame.date == date(2030, 2, 5)
    assert d.state == State.OFFER_SLOTS


# --- misheard / colloquial departments ------------------------------------------


@pytest.mark.parametrize(
    ("utterance", "department"),
    [
        ("I need cardio logy", "Cardiology"),
        ("appointment with the skin doctor", "Dermatology"),
        ("I want a heart doctor", "Cardiology"),
        ("kids doctor please", "Pediatrics"),
    ],
)
def test_misheard_or_colloquial_department(call, utterance, department):
    c = call()
    d = c.say(utterance)
    assert d.frame.department == department
    assert d.expected_slot == "date"


# --- unknown department ---------------------------------------------------------


def test_unknown_department_lists_what_is_offered(call):
    c = call()
    d = c.say("I need a dentist")
    assert "don't" in d.reply_text
    assert "Cardiology" in d.reply_text and "Dermatology" in d.reply_text
    assert d.expected_slot == "department"
    d = c.say("general medicine then")
    assert d.frame.department == "General Medicine"


# --- yes / no / something else at confirmation ------------------------------------


def reach_confirmation(c):
    c.say("Book me with a dermatologist next Monday at 10 am")
    c.say("Ali Raza")
    return c.say("03001234567")


def test_no_at_confirmation_then_change_the_time(call, clinic):
    c = call()
    reach_confirmation(c)
    d = c.say("no")
    assert d.state == State.COLLECT_SLOTS
    assert "what would you like to change" in d.reply_text.lower()
    d = c.say("the time")
    assert d.state == State.OFFER_SLOTS
    c.say("the third one")
    d = c.say("yes")
    assert d.action == "booked"
    assert appointment_count(clinic) == 1


def test_unrelated_answer_at_confirmation(call, clinic):
    c = call()
    reach_confirmation(c)
    d = c.say("purple elephant banana")
    assert d.state == State.CONFIRM
    assert d.action == "not_understood"
    assert "yes or" in d.reply_text
    assert appointment_count(clinic) == 0
    assert c.say("yes").action == "booked"


def test_question_at_confirmation_is_answered_then_confirmation_repeated(call):
    c = call()
    confirm = reach_confirmation(c).reply_text
    d = c.say("where is the clinic")
    assert "Jasmine Road" in d.reply_text
    assert d.reply_text.endswith(confirm)
    assert d.state == State.CONFIRM


# --- repeat ------------------------------------------------------------------


@pytest.mark.parametrize("ask_again", ["repeat that", "what?", "sorry, I didn't catch that"])
def test_repeat_resends_last_prompt(call, ask_again):
    c = call()
    prompt = c.say("cardiology on Friday").reply_text
    d = c.say(ask_again)
    assert d.reply_text == prompt
    assert d.state == State.OFFER_SLOTS


# --- silence -------------------------------------------------------------------


def test_silence_reprompts_then_ends_after_three(call):
    c = call()
    question = c.say("I want to book a cardiologist").reply_text
    d = c.say("")
    assert d.action == "silence"
    assert d.reply_text.endswith(question)
    d = c.say("   ")
    assert not d.end_call
    d = c.say("")
    assert (d.state, d.action, d.end_call) == (State.END, "ended_silence", True)


def test_silence_counter_resets_when_caller_speaks(call):
    c = call()
    c.say("I want to book a cardiologist")
    c.say("")
    c.say("")
    d = c.say("friday")
    assert d.frame.silence_count == 0
    assert not c.say("").end_call


# --- out of scope -----------------------------------------------------------------


def test_out_of_scope_steers_back(call):
    c = call()
    question = c.say("I want to book a cardiologist").reply_text
    d = c.say("what's the weather today")
    assert "only help with appointments" in d.reply_text
    assert d.reply_text.endswith(question)
    assert d.frame.date is None  # "today" inside the question is not a booking date
    assert d.expected_slot == "date"


# --- abort mid-booking ------------------------------------------------------------


@pytest.mark.parametrize("give_up", ["forget it", "never mind"])
def test_abort_mid_booking(call, clinic, give_up):
    c = call()
    c.say("Book me with a dermatologist next Monday at 10 am")
    c.say("Ali Raza")
    d = c.say(give_up)
    assert (d.state, d.action) == (State.IDENTIFY_TASK, "aborted")
    assert d.frame.task is None
    assert d.frame.department is None and d.frame.chosen_slot is None
    assert appointment_count(clinic) == 0


# --- invalid phone -------------------------------------------------------------------


def test_invalid_phone_asks_again_with_format_hint(call, clinic):
    c = call()
    c.say("Book me with a dermatologist next Monday at 10 am")
    c.say("Ali Raza")
    d = c.say("my number is 0321")
    assert "11-digit" in d.reply_text and "03" in d.reply_text
    assert d.expected_slot == "phone"
    d = c.say("12345678")
    assert d.expected_slot == "phone"
    d = c.say("0321 5551234")
    assert d.state == State.CONFIRM
    assert c.say("yes").action == "booked"


# --- booking reference not found -----------------------------------------------------


def test_reference_not_found_on_cancel(call):
    c = call()
    c.say("I want to cancel my appointment")
    d = c.say("SC-ZZZZ")
    assert "couldn't find" in d.reply_text
    assert d.state == State.LOOKUP_BOOKING
    assert d.frame.appointment is None


def test_reference_not_found_on_reschedule_then_found_by_phone(call):
    c = call()
    slot = c.repo.find_free_slots("ENT", FRIDAY, limit=1)[0]
    existing = c.repo.book_slot(slot.id, "Iqra Butt", "03005550112")
    c.say("I need to reschedule my booking SC-ZZZZ")
    assert "couldn't find" in c.last.reply_text
    d = c.say("my number is 03005550112")
    assert d.frame.appointment.booking_ref == existing.booking_ref


def test_cancelled_booking_cannot_be_cancelled_again(call):
    c = call()
    slot = c.repo.find_free_slots("ENT", FRIDAY, limit=1)[0]
    existing = c.repo.book_slot(slot.id, "Iqra Butt", "03005550112")
    c.repo.cancel_appointment(existing.booking_ref)
    d = c.say(f"cancel my appointment {existing.booking_ref}")
    assert "couldn't find" in d.reply_text


# --- double-booking race -----------------------------------------------------------------


def test_slot_taken_between_offer_and_confirm(call, clinic):
    c = call()
    d = reach_confirmation(c)
    wanted = d.frame.chosen_slot
    # someone else books the same slot while our caller is confirming
    c.repo.book_slot(wanted.slot_id, "Someone Else", "03009998888")

    d = c.say("yes")
    assert (d.state, d.action) == (State.OFFER_SLOTS, "slot_unavailable")
    assert wanted.slot_id not in {o.slot_id for o in d.frame.candidate_slots}
    assert len(d.frame.candidate_slots) == 3

    c.say("the first one")
    d = c.say("yes")  # name and phone were kept
    assert d.action == "booked"
    mine = get_appointment(clinic, ref=d.frame.booking_ref)
    assert mine.slot_id != wanted.slot_id
    assert mine.patient.name == "Ali Raza"


# --- emergency overrides everything -----------------------------------------------------


@pytest.mark.parametrize(
    "steps",
    [
        [],
        ["I want to book a cardiologist"],
        ["Book me with a dermatologist next Monday at 10 am", "Ali Raza", "03001234567"],
    ],
    ids=["at greeting", "mid booking", "at confirmation"],
)
def test_emergency_at_any_point(call, clinic, steps):
    c = call()
    for step in steps:
        c.say(step)
    d = c.say("my father has chest pain and can't breathe")
    assert (d.state, d.action, d.end_call) == (State.EMERGENCY, "emergency", True)
    assert "1122" in d.reply_text
    assert appointment_count(clinic) == 0
    assert c.say("yes").reply_text == "This call has ended."


# --- hand-off ---------------------------------------------------------------------------


def test_human_agent_request(call):
    c = call()
    c.say("I want to book a cardiologist")
    d = c.say("can I speak to a real person")
    assert (d.state, d.action, d.end_call) == (State.HANDOFF, "handoff", True)


def test_three_misunderstandings_in_a_row_hand_off(call):
    c = call()
    c.say("I want to book a cardiologist")
    for _ in range(2):
        d = c.say("blorp zxqv")
        assert d.action == "not_understood"
    d = c.say("blorp zxqv")
    assert (d.state, d.action, d.end_call) == (State.HANDOFF, "handoff", True)


def test_misunderstanding_counter_resets_after_an_understood_turn(call):
    c = call()
    c.say("I want to book a cardiologist")
    c.say("blorp zxqv")
    c.say("blorp zxqv")
    d = c.say("friday")
    assert d.frame.fail_count == 0
    assert c.say("blorp zxqv").state != State.HANDOFF


def test_booked_appointment_status(call, clinic):
    c = call()
    reach_confirmation(c)
    ref = c.say("yes").frame.booking_ref
    assert get_appointment(clinic, ref=ref).status == AppointmentStatus.BOOKED
