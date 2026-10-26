"""Focused regression coverage for Phase 2 parser and FSM repairs."""

from datetime import datetime

import pytest

from app.brain.engine import ConversationEngine
from app.brain.parser import IntentParser
from app.brain.responses import ask_what_to_change, invalid_date_past
from app.brain.states import Intent


REF = datetime(2025, 1, 15, 10)
DETAILS = {"date": "2025-01-16", "time": "19:00", "party_size": 4}
EMPTY = {"date": None, "time": None, "party_size": None}


def start(*turns):
    engine = ConversationEngine(reference_date=REF)
    sid = engine.create_session()
    engine.start_conversation(sid)
    for turn in turns:
        engine.process_input(sid, turn)
    return engine, sid


def ready():
    return start("tomorrow at 7pm for 4")


@pytest.mark.parametrize(
    "text",
    ["no", "not correct", "that's wrong", "incorrect", "not right", "no, correct",
     "that\u2019s wrong", "don\u2019t book", "not sure", "not quite right", "I don't think that's correct"],
)
def test_rejections_never_complete(text):
    assert IntentParser().parse(text, REF).intent == Intent.DENY
    engine, sid = ready()
    response = engine.process_input(sid, text)
    assert response.state == "confirm"
    assert response.collected_data == DETAILS
    assert response.message == ask_what_to_change()


@pytest.mark.parametrize("text", ["yes", "correct", "that's right", "book it", "sounds good"])
def test_valid_affirmations_complete(text):
    engine, sid = ready()
    response = engine.process_input(sid, text)
    assert response.state == "completed"
    assert response.collected_data == DETAILS
    assert "confirmed" in response.message.lower()


@pytest.mark.parametrize(
    "text", ["7:99pm", "25:00", "13:75", "0pm", "13am", "7:99 pm", "19:30:99pm",
             "7:-3pm", "-2 o'clock"]
)
def test_invalid_times_are_not_salvaged(text):
    parsed = IntentParser().parse(text, REF)
    assert parsed.time is None
    assert parsed.raw_number is None
    assert parsed.time_error == "invalid"
    engine, sid = start("tomorrow")
    response = engine.process_input(sid, text)
    assert response.state == "ask_time"
    assert response.collected_data == {**EMPTY, "date": DETAILS["date"]}
    assert "valid" in response.message.lower()
    assert "time" in response.message.lower()


@pytest.mark.parametrize("text", ["February 30", "April 31", "2025-02-30", "2/30"])
def test_impossible_dates_are_not_salvaged(text):
    parsed = IntentParser().parse(text, REF)
    assert parsed.date is None
    assert parsed.raw_number is None
    assert parsed.date_error == "invalid"
    engine, sid = start()
    response = engine.process_input(sid, text)
    assert response.state == "ask_date"
    assert response.collected_data == EMPTY
    assert "valid" in response.message.lower()
    assert "date" in response.message.lower()


@pytest.mark.parametrize("text", ["yesterday", "2025-01-10", "January 10, 2025", "1/10/2025"])
def test_past_dates_are_rejected_exactly(text):
    engine, sid = start()
    response = engine.process_input(sid, text)
    assert response.state == "ask_date"
    assert response.collected_data == EMPTY
    assert response.message == invalid_date_past()


def test_yearless_past_month_still_rolls_forward_and_respects_booking_window():
    parsed = IntentParser().parse("January 10", REF)
    assert parsed.date == "2026-01-10"
    engine, sid = start()
    response = engine.process_input(sid, "January 10")
    assert response.state == "ask_date"
    assert response.collected_data == EMPTY
    assert "90 days" in response.message


@pytest.mark.parametrize(
    "text,state,data",
    [("for 7 pm", "ask_date", {**EMPTY, "time": "19:00"}),
     ("for 20 January", "ask_time", {**EMPTY, "date": "2025-01-20"})],
)
def test_date_and_time_numbers_are_not_also_guest_counts(text, state, data):
    parsed = IntentParser().parse(text, REF)
    assert parsed.party_size is None
    engine, sid = start()
    response = engine.process_input(sid, text)
    assert response.state == state
    assert response.collected_data == data


@pytest.mark.parametrize("text,count", [("-2 people", -2), ("0 guests", 0), ("for -2", -2)])
def test_nonpositive_guest_counts_rejected_before_storage(text, count):
    assert IntentParser().parse(text, REF).party_size == count
    engine, sid = start("tomorrow at 7pm")
    response = engine.process_input(sid, text)
    assert response.state == "ask_party_size"
    assert response.collected_data == {**DETAILS, "party_size": None}
    assert "at least 1" in response.message


@pytest.mark.parametrize("text,count,prompt", [("100 people", 100, "20"), ("-100 people", -100, "at least 1")])
def test_large_guest_counts_are_not_truncated(text, count, prompt):
    assert IntentParser().parse(text, REF).party_size == count
    engine, sid = start("tomorrow at 7pm")
    response = engine.process_input(sid, text)
    assert response.state == "ask_party_size"
    assert response.collected_data == {**DETAILS, "party_size": None}
    assert prompt in response.message


def test_ambiguous_time_requires_choice_and_then_recovers():
    parsed = IntentParser().parse("7pm or 8pm", REF)
    assert parsed.time is None
    assert parsed.raw_number is None
    assert parsed.time_error == "ambiguous"
    engine, sid = start("tomorrow for 4")
    response = engine.process_input(sid, "7pm or 8pm")
    assert response.state == "ask_time"
    assert response.collected_data == {**DETAILS, "time": None}
    assert "choose" in response.message.lower()
    assert "one" in response.message.lower()
    response = engine.process_input(sid, "8pm")
    assert response.state == "confirm"
    assert response.collected_data == {**DETAILS, "time": "20:00"}


@pytest.mark.parametrize(
    "text,state,missing",
    [
        ("tomorrow at 7:99pm for 4", "ask_time", "time"),
        ("February 30 at 7pm for 4", "ask_date", "date"),
        ("tomorrow at 7pm for -2", "ask_party_size", "party_size"),
    ],
)
def test_invalid_field_does_not_discard_other_valid_information(text, state, missing):
    engine, sid = start()
    response = engine.process_input(sid, text)
    assert response.state == state
    assert response.collected_data == {**DETAILS, missing: None}


@pytest.mark.parametrize(
    "text,field,state,recovery,value,prompt",
    [
        ("actually 50 people", "party_size", "ask_party_size", "6", 6, "20"),
        ("change the number of guests to -2", "party_size", "ask_party_size", "6 people", 6, "at least 1"),
        ("actually February 30", "date", "ask_date", "Friday", "2025-01-17", "valid"),
        ("change the date to April 31", "date", "ask_date", "Friday", "2025-01-17", "valid"),
        ("actually 2025-01-10", "date", "ask_date", "Friday", "2025-01-17", "past"),
        ("actually 7:99pm", "time", "ask_time", "8pm", "20:00", "valid"),
        ("change the time to 3am", "time", "ask_time", "8pm", "20:00", "hours"),
        ("actually 7pm or 8pm", "time", "ask_time", "8pm", "20:00", "choose"),
    ],
)
def test_invalid_corrections_clear_slot_and_require_valid_replacement(
    text, field, state, recovery, value, prompt
):
    engine, sid = ready()
    response = engine.process_input(sid, text)
    expected = {**DETAILS, field: None}
    assert response.state == state
    assert response.collected_data == expected
    assert prompt in response.message.lower()
    for unexpected in ("hello", "yes"):
        response = engine.process_input(sid, unexpected)
        assert response.state == state
        assert response.collected_data == expected
    response = engine.process_input(sid, recovery)
    assert response.state == "confirm"
    assert response.collected_data == {**DETAILS, field: value}
    assert engine.process_input(sid, "yes").state == "completed"


@pytest.mark.parametrize(
    "text,changes",
    [
        ("change the time to 8pm", {"time": "20:00"}),
        ("change the time to 8", {"time": "20:00"}),
        ("change the number of guests to 6", {"party_size": 6}),
        ("change the date to Friday", {"date": "2025-01-17"}),
        ("actually 6 people", {"party_size": 6}),
        ("no, make it 6 people", {"party_size": 6}),
        ("change the time to 8pm for 6 people", {"time": "20:00", "party_size": 6}),
    ],
)
def test_valid_corrections_reconfirm_instead_of_completing(text, changes):
    engine, sid = ready()
    response = engine.process_input(sid, text)
    assert response.state == "confirm"
    assert response.collected_data == {**DETAILS, **changes}
    assert "Shall I" in response.message


@pytest.mark.parametrize("terminal", ["completed", "cancelled"])
@pytest.mark.parametrize(
    "text",
    ["change the time to 8pm", "change the date", "actually 6 people", "Friday at 8pm for 6", "cancel", "hello"],
)
def test_terminal_sessions_ignore_ordinary_changes(terminal, text):
    engine, sid = ready()
    engine.process_input(sid, "yes" if terminal == "completed" else "cancel")
    response = engine.process_input(sid, text)
    assert response.state == terminal
    assert response.collected_data == DETAILS
    assert "start over" in response.message.lower()
    if terminal == "completed":
        assert "already" in response.message.lower()


@pytest.mark.parametrize("terminal", ["completed", "cancelled"])
def test_restart_is_explicit_escape_from_terminal_session(terminal):
    engine, sid = ready()
    engine.process_input(sid, "yes" if terminal == "completed" else "cancel")
    response = engine.process_input(sid, "start over")
    assert response.state == "ask_date"
    assert response.collected_data == EMPTY
    response = engine.process_input(sid, "Friday at 8pm for 2")
    assert response.state == "confirm"
    assert response.collected_data == {"date": "2025-01-17", "time": "20:00", "party_size": 2}


def test_normal_flow_rejection_correction_and_confirmation():
    engine, sid = start()
    assert engine.process_input(sid, "hello").state == "ask_date"
    assert engine.process_input(sid, "tomorrow").state == "ask_time"
    assert engine.process_input(sid, "7pm").state == "ask_party_size"
    assert engine.process_input(sid, "4").state == "confirm"
    assert engine.process_input(sid, "incorrect").state == "confirm"
    response = engine.process_input(sid, "actually 6 people")
    assert response.state == "confirm"
    assert response.collected_data == {**DETAILS, "party_size": 6}
    assert engine.process_input(sid, "book it").state == "completed"


def test_invalid_turn_does_not_affect_another_session():
    engine, sid = ready()
    other = engine.create_session()
    engine.start_conversation(other)
    engine.process_input(other, "Friday at 8pm for 2")
    assert engine.process_input(sid, "actually 50 people").state == "ask_party_size"
    response = engine.process_input(other, "yes")
    assert response.state == "completed"
    assert response.collected_data == {"date": "2025-01-17", "time": "20:00", "party_size": 2}
