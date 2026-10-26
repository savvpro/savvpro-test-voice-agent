from brain.availability import TAKEN_SLOTS
from brain.brain import handle_turn, speak_date, speak_time
from brain.state import Session


def turn(session, text):
    return handle_turn(session, text)


def test_speak_time_formats_human_friendly_values():
    assert speak_time("14:00") == "2 PM"
    assert speak_time("09:30") == "9:30 AM"
    assert speak_time("12:00") == "12 PM"


def test_speak_date_formats_weekday_month_and_day():
    assert speak_date("2026-10-29") == "Thursday, October 29"


def test_multi_slot_and_mid_call_change():
    session = Session()
    session, _, _ = turn(session, "I need an appointment")
    session, _, _ = turn(session, "Tuesday at 2pm for a checkup")
    assert session.slots["date"]
    assert session.slots["time"] == "14:00"
    assert session.slots["reason"] == "checkup"
    old_date = session.slots["date"]
    session, _, _ = turn(session, "Actually, Wednesday")
    assert session.slots["date"] != old_date
    assert session.slots["time"] == "14:00"


def test_taken_time_offers_two_alternatives():
    session = Session()
    date, time = next(iter(TAKEN_SLOTS))
    session, reply, _ = turn(session, f"book a checkup on {date} at {time}")
    session, reply, _ = turn(session, "Alex Example")
    session, reply, _ = turn(session, "5551234567")
    assert session.current_state == "COLLECTING"
    assert "available" in reply.lower()
    assert "or" in reply.lower()


def test_negated_date_clears_slot_but_does_not_confirm():
    session = Session(slots={"date": "2030-01-15"})
    session, _, _ = turn(session, "no, not Monday")
    assert session.current_state == "COLLECTING"
    assert "date" not in session.slots


def test_cancel_empty_and_vague_inputs():
    session = Session()
    session, _, _ = turn(session, "I want an appointment")
    state = session.current_state
    session, reply, _ = turn(session, "sometime next week")
    assert session.current_state == state
    assert "date" in reply.lower()
    session, reply, _ = turn(session, "???")
    assert session.current_state == state
    assert "didn't catch" in reply
    session, reply, _ = turn(session, "cancel")
    assert session.current_state == "CANCELLED"
    assert "cancel" in reply.lower()


def test_happy_path_and_confirmation_no():
    session = Session()
    session, _, _ = turn(session, "book a checkup on 2030-01-16 at 10am")
    session, _, _ = turn(session, "Jordan Example")
    session, _, _ = turn(session, "5559876543")
    assert session.current_state == "CONFIRMING"
    session, reply, _ = turn(session, "no")
    assert session.current_state == "CONFIRMING"
    assert "change" in reply.lower()
    session, reply, _ = turn(session, "yes")
    assert session.current_state == "BOOKED"
    assert "booked" in reply.lower()


def test_decision_payload_on_mid_collection_turn():
    session = Session()
    session, _, decision = turn(session, "I need an appointment")
    assert decision == {
        "intent": "book",
        "slots": {},
        "state": "COLLECTING",
        "pending_slot": "date",
    }


def test_pending_time_reprompts_for_meridiem_without_filling_slot():
    session = Session(current_state="COLLECTING", pending_slot="time",
                     slots={"date": "2030-01-16"})
    session, reply, decision = turn(session, "around 2 ish")
    assert session.current_state == "COLLECTING"
    assert "time" not in session.slots
    assert "am or pm" in reply
    assert decision["pending_slot"] == "time"


def test_filler_answer_while_waiting_for_time_leaves_state_and_slots_unchanged():
    session = Session(current_state="COLLECTING", pending_slot="time",
                     slots={"date": "2030-01-16"})
    session, reply, decision = turn(session, "whatever works")
    assert session.current_state == "COLLECTING"
    assert session.slots == {"date": "2030-01-16"}
    assert "didn't catch" in reply
    assert decision["pending_slot"] == "time"


def test_filler_only_answer_while_waiting_for_reason_reprompts():
    session = Session(current_state="COLLECTING", pending_slot="reason",
                     slots={"date": "2030-01-16", "time": "10:00"})
    session, reply, _ = turn(session, "idk")
    assert "didn't catch" in reply
    assert "reason" not in session.slots


def test_unclear_confirmation_uses_confirmation_prompt():
    session = Session(current_state="CONFIRMING", slots={
        "date": "2030-01-16",
        "time": "10:00",
        "reason": "checkup",
        "patient_name": "Jordan Example",
        "phone": "5559876543",
    })
    session, reply, decision = turn(session, "maybe")
    assert session.current_state == "CONFIRMING"
    assert decision["intent"] == "unclear"
    assert reply == "Please say yes to confirm, or tell me what to change."


def test_confirming_slot_change_takes_precedence_over_confirm_no():
    session = Session(current_state="CONFIRMING", slots={
        "date": "2030-01-16",
        "time": "14:00",
        "reason": "checkup",
        "patient_name": "Jordan Example",
        "phone": "5559876543",
    })
    session, reply, decision = turn(session, "actually make it 3pm not 2")
    assert session.current_state == "CONFIRMING"
    assert session.slots["time"] == "15:00"
    assert "3 PM" in reply
    assert decision["intent"] == "change"
    assert session.awaiting_change_field is False


def test_confirm_no_then_field_name_clears_slot_and_collects_new_value():
    session = Session(current_state="CONFIRMING", slots={
        "date": "2030-01-16",
        "time": "14:00",
        "reason": "checkup",
        "patient_name": "Jordan Example",
        "phone": "5559876543",
    })
    session, reply, _ = turn(session, "no")
    assert session.awaiting_change_field is True
    assert "change" in reply.lower()

    session, reply, decision = turn(session, "time")
    assert session.current_state == "COLLECTING"
    assert "time" not in session.slots
    assert session.pending_slot == "time"
    assert session.awaiting_change_field is False
    assert "time" in reply.lower()
    assert decision["pending_slot"] == "time"


def test_name_step_rejects_garbage_name():
    session = Session(current_state="COLLECTING", pending_slot="patient_name",
                      slots={"date": "2030-01-16", "time": "10:00", "reason": "checkup"})
    session, reply, _ = turn(session, "aass")
    assert "patient_name" not in session.slots
    assert "full name" in reply.lower()


def test_name_step_change_phrase_updates_date_without_storing_name():
    session = Session(current_state="COLLECTING", pending_slot="patient_name",
                      slots={"date": "2030-01-16", "time": "10:00", "reason": "checkup"})
    session, reply, _ = turn(session, "actually make it friday")
    assert "patient_name" not in session.slots
    assert session.slots["date"] != "2030-01-16"
    assert "full name" in reply.lower()


def test_before_hours_uses_opening_hours_message():
    session = Session(slots={
        "date": "2030-01-16",
        "time": "07:00",
        "reason": "checkup",
        "patient_name": "Jordan Example",
        "phone": "5559876543",
    })
    session, reply, _ = turn(session, "book")
    assert session.current_state == "COLLECTING"
    assert "open 9am to 5pm" in reply.lower()
