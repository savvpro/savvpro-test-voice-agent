import pytest

from brain import availability
from brain.brain import handle_turn
from brain.state import BOOKED, CANCELLED, COLLECTING, CONFIRMING, Session


@pytest.fixture(autouse=True)
def reset_fake_store():
    taken = set(availability.TAKEN_SLOTS)
    bookings = list(availability.BOOKINGS)
    yield
    availability.TAKEN_SLOTS.clear()
    availability.TAKEN_SLOTS.update(taken)
    availability.BOOKINGS[:] = bookings


def turn(session, text):
    return handle_turn(session, text)


def _ready_session():
    session = Session()
    session, _, _ = turn(session, "book a checkup on 2030-01-20 at 10am")
    session, _, _ = turn(session, "Jordan Example")
    session, _, _ = turn(session, "5559876543")
    return session


def test_happy_path_books_appointment():
    """A complete appointment flow ends in BOOKED after confirmation."""
    session = Session()
    session, _, _ = turn(session, "book a checkup on 2030-01-20 at 10am")
    session, _, _ = turn(session, "Jordan Example")
    session, _, _ = turn(session, "5559876543")
    session, reply, _ = turn(session, "yes")
    assert session.current_state == BOOKED
    assert "booked" in reply.lower()


def test_multi_slot_single_utterance_fills_three_slots():
    """One utterance fills reason, date, and time before asking for a name."""
    session, reply, _ = turn(Session(), "book a follow-up on friday at 11am")
    assert session.slots["reason"] == "follow-up"
    assert session.slots["time"] == "11:00"
    assert session.slots["date"]
    assert session.pending_slot == "patient_name"
    assert "full name" in reply.lower()


def test_midcall_change_during_collection_updates_date():
    """Changing the date during collection preserves the other collected slots."""
    session = Session()
    session, _, _ = turn(session, "book a checkup on 2030-01-20 at 10am")
    old_time = session.slots["time"]
    session, _, _ = turn(session, "actually make it 2030-01-21")
    assert session.slots["date"] == "2030-01-21"
    assert session.slots["time"] == old_time
    assert session.current_state == COLLECTING


def test_midcall_change_at_confirmation_updates_time():
    """A confirmation-time correction updates time and returns to confirmation."""
    session = _ready_session()
    assert session.current_state == CONFIRMING
    session, reply, decision = turn(session, "actually make it 3pm not 2")
    assert session.current_state == CONFIRMING
    assert session.slots["time"] == "15:00"
    assert "3 PM" in reply
    assert decision["intent"] == "change"


@pytest.mark.parametrize("word", ["yeah", "ok", "yep", "sure"])
def test_confirmation_accepts_varied_yes_words(word):
    """Common affirmative confirmation words book the appointment."""
    session = _ready_session()
    session, reply, _ = turn(session, word)
    assert session.current_state == BOOKED
    assert "booked" in reply.lower()


def test_confirmation_no_then_change_field():
    """A negative confirmation selects a field, collects its replacement, and re-confirms."""
    session = _ready_session()
    session, reply, _ = turn(session, "no")
    assert session.awaiting_change_field is True
    assert "which detail" in reply.lower()
    session, reply, _ = turn(session, "time")
    assert session.current_state == COLLECTING
    assert "time" not in session.slots
    assert "time" in reply.lower()
    session, _, _ = turn(session, "3pm")
    assert session.slots["time"] == "15:00"
    assert session.current_state == CONFIRMING


def test_ambiguous_time_asks_am_or_pm():
    """A bare hour does not fill time and asks for a meridiem."""
    session = Session(current_state=COLLECTING, pending_slot="time",
                      slots={"date": "2030-01-20"})
    session, reply, _ = turn(session, "at 7")
    assert "time" not in session.slots
    assert "am or pm" in reply.lower()


def test_messy_time_filler_asks_am_pm():
    """Filler around a bare hour remains ambiguous instead of assuming morning or evening."""
    session = Session(current_state=COLLECTING, pending_slot="time",
                      slots={"date": "2030-01-20"})
    session, reply, _ = turn(session, "around 2 ish")
    assert "time" not in session.slots
    assert "am or pm" in reply.lower()


def test_filler_does_not_fill_name_slot():
    """Filler text at the name step is rejected and does not become a patient name."""
    session = Session(current_state=COLLECTING, pending_slot="patient_name",
                      slots={"date": "2030-01-20", "time": "10:00", "reason": "checkup"})
    session, reply, _ = turn(session, "whatever works")
    assert "patient_name" not in session.slots
    assert "full name" in reply.lower()


def test_vague_date_reprompts_for_concrete_date():
    """A vague date leaves the date empty and requests a concrete date."""
    session = Session(current_state=COLLECTING, pending_slot="date")
    session, reply, _ = turn(session, "sometime next week")
    assert "date" not in session.slots
    assert "concrete date" in reply.lower()


def test_short_phone_rejected():
    """A short phone answer is rejected before a valid phone number is accepted."""
    session = Session(current_state=COLLECTING, pending_slot="phone",
                      slots={"date": "2030-01-20", "time": "10:00", "reason": "checkup",
                             "patient_name": "Jordan Example"})
    session, reply, _ = turn(session, "02")
    assert "phone" not in session.slots
    assert "phone" in reply.lower()
    session, _, _ = turn(session, "5559876543")
    assert session.slots["phone"] == "5559876543"


def test_taken_slot_offers_alternatives_and_books_picked():
    """A taken slot offers alternatives, and selecting one can complete booking."""
    availability.TAKEN_SLOTS.add(("2030-01-20", "14:00"))
    session = Session()
    session, reply, _ = turn(session, "book a checkup on 2030-01-20 at 2pm")
    session, _, _ = turn(session, "Jordan Example")
    session, reply, _ = turn(session, "5559876543")
    assert session.current_state == COLLECTING
    assert "available" in reply.lower()
    assert "or" in reply.lower()
    session, _, _ = turn(session, "2:30pm")
    assert session.current_state == CONFIRMING
    session, _, _ = turn(session, "yes")
    assert session.current_state == BOOKED


def test_cancel_midflow_ends_cleanly():
    """Cancellation during collection ends the session cleanly."""
    session, _, _ = turn(Session(), "book an appointment")
    session, reply, _ = turn(session, "cancel")
    assert session.current_state == CANCELLED
    assert "cancel" in reply.lower()


def test_out_of_scope_declines_politely():
    """An unsupported service is declined while steering back to appointments."""
    session, reply, _ = turn(Session(), "do you do dental?")
    assert session.current_state != BOOKED
    assert "appointment" in reply.lower()
    assert "only" in reply.lower()


def test_empty_and_garbage_input_keeps_state():
    """Empty and random input preserve state and pending slot with a retry prompt."""
    session, _, _ = turn(Session(), "book an appointment")
    original_state, original_pending = session.current_state, session.pending_slot
    session, reply, _ = turn(session, "")
    assert "didn't catch" in reply.lower()
    assert session.current_state == original_state
    assert session.pending_slot == original_pending
    session, reply, _ = turn(session, "asdf")
    assert "didn't catch" in reply.lower()
    assert session.current_state == original_state
    assert session.pending_slot == original_pending


def test_name_step_rejects_change_utterance():
    """A change utterance at the name step updates the real slot but not the name."""
    session = Session(current_state=COLLECTING, pending_slot="patient_name",
                      slots={"date": "2030-01-20", "time": "10:00", "reason": "checkup"})
    session, _, _ = turn(session, "actually make it friday")
    assert "patient_name" not in session.slots
    assert session.slots["date"] != "2030-01-20"


def test_name_step_rejects_junk_name():
    """Repeated-character junk names are rejected and request a full name."""
    session = Session(current_state=COLLECTING, pending_slot="patient_name",
                      slots={"date": "2030-01-20", "time": "10:00", "reason": "checkup"})
    for junk in ("aass", "dd"):
        session, reply, _ = turn(session, junk)
        assert "patient_name" not in session.slots
        assert "full name" in reply.lower()


def test_dot_minute_separator_parses():
    """A dot-separated minute value parses into 24-hour time."""
    session, _, _ = turn(Session(current_state=COLLECTING, pending_slot="time",
                                  slots={"date": "2030-01-20"}), "3.30 pm")
    assert session.slots["time"] == "15:30"


def test_outside_working_hours_message():
    """A before-hours request reports opening hours rather than a taken slot."""
    session = Session(slots={
        "date": "2030-01-20", "time": "07:00", "reason": "checkup",
        "patient_name": "Jordan Example", "phone": "5559876543",
    })
    session, reply, _ = turn(session, "book")
    assert "open 9am to 5pm" in reply.lower()
    assert "not available" not in reply.lower()
