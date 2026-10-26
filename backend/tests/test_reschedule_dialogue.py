"""Reschedule request families, destination answers and safe contextual recovery."""
import pytest

from app.brain.language import recognize
from app.schemas import Intent
from conftest import book, new_session, turn


@pytest.mark.parametrize("text", [
    "All right I want you to change the timing for this appointment",
    "change the time of my appointment",
    "Could you adjust the time for that booking",
    "change this appointment's time",
    "Please update my booking time",
])
def test_time_change_requests_ask_for_new_time_and_keep_the_saved_date(client, text):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, text)
    assert c["current_intent"] == Intent.RESCHEDULE
    assert c["missing_information"] == ["time"]
    assert c["entities"]["date"] == original["starts_at"][:10]
    assert c["entities"]["time"] is None
    assert c["proposed_action"] is None
    c = turn(client, c, "5 PM")
    assert c["proposed_action"] == "reschedule"
    assert c["entities"]["time"] == "17:00"
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


@pytest.mark.parametrize("text", [
    "change the date for my booking",
    "adjust the day of this appointment",
    "change this appointment date",
])
def test_date_change_requests_ask_for_new_date_and_keep_the_saved_time(client, text):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, text)
    assert c["missing_information"] == ["date"]
    assert c["entities"]["time"] == original["starts_at"][11:16]
    c = turn(client, c, "Friday")
    assert c["proposed_action"] == "reschedule"
    assert c["entities"]["date"] == "2026-10-30"
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


@pytest.mark.parametrize("utterance", [
    "reschedule the appointment", "And rescheduled the appointment",
    "please rescheduled my booking", "Can you reschedule it",
])
@pytest.mark.parametrize("answer", ["5 PM", "Friday"])
def test_open_reschedule_question_accepts_either_date_or_time(client, utterance, answer):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, utterance)
    assert c["missing_information"] == ["date", "time"]
    assert "new date or time" in c["reply"].lower()
    assert c["proposed_action"] is None
    c = turn(client, c, answer)
    assert c["proposed_action"] == "reschedule"
    assert c["entities"]["date"] == ("2026-10-30" if answer == "Friday" else original["starts_at"][:10])
    assert c["entities"]["time"] == ("17:00" if answer == "5 PM" else "15:00")
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


@pytest.mark.parametrize("answer", [
    "Change diamond from 4:00 p.m. To 5:00 p.m.",
    "They scheduled that appointment from 4:00 p.m. To 5:00 p.m.",
    "from 4 PM to 5 PM",
])
def test_directional_answer_in_active_reschedule_uses_destination_without_a_write(client, answer):
    c = book(client, "book a beard cut on December 15 2026 at 4 PM")
    original = c["appointment"]
    c = turn(client, c, "I want you to change the timing for this appointment")
    c = turn(client, c, answer)
    assert c["proposed_action"] == "reschedule"
    assert c["entities"]["date"] == "2026-12-15"
    assert c["entities"]["time"] == "17:00"
    assert client.get(f"/api/appointments/{original['reference']}").json() == original
    c = turn(client, c, "yes")
    assert c["appointment"]["starts_at"] == "2026-12-15T17:00:00+05:00"


@pytest.mark.parametrize("text", [
    "They rescheduled the appointment from 4 PM to 5 PM",
    "They scheduled that appointment from 4 PM to 5 PM",
    "Change diamond from 4 PM to 5 PM",
])
def test_reported_or_garbled_words_cannot_start_rescheduling_without_context(client, text):
    assert recognize(text).intent == Intent.UNKNOWN
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, text)
    assert c["proposed_action"] is None
    c = turn(client, c, "yes")
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


@pytest.mark.parametrize("text,intent", [
    ("How can I change the timing for my appointment?", Intent.INFO),
    ("Don't change the timing for this appointment", Intent.DENY),
    ("Do not adjust the date for my booking", Intent.DENY),
])
def test_schedule_request_families_respect_questions_and_negation(text, intent):
    assert recognize(text).intent == intent


def test_new_session_still_requires_a_reference_for_time_changes(client):
    book(client)
    c = turn(client, new_session(client), "change the timing for this appointment")
    assert c["missing_information"] == ["reference"]
    assert c["proposed_action"] is None


def test_unspecified_new_time_clears_a_ready_proposal(client):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "reschedule it to 5 PM")
    c = turn(client, c, "change the time of this appointment")
    assert c["missing_information"] == ["time"]
    assert c["proposed_action"] is None
    c = turn(client, c, "yes")
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


def test_repeating_a_time_request_cannot_restore_a_rejected_date(client):
    c = book(client)
    c = turn(client, c, "reschedule to November 31 2026 at 5 PM")
    c = turn(client, c, "change the timing for this appointment")
    assert c["entities"]["date"] is None
    assert "date" in c["rejected_fields"]
    c = turn(client, c, "6 PM")
    assert c["entities"]["date"] is None
    assert c["proposed_action"] is None


def test_alternative_times_are_not_a_directional_answer(client):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "reschedule the appointment")
    c = turn(client, c, "4 PM or 5 PM")
    assert c["entities"]["time"] is None
    assert c["proposed_action"] is None
    c = turn(client, c, "yes")
    assert client.get(f"/api/appointments/{original['reference']}").json() == original
