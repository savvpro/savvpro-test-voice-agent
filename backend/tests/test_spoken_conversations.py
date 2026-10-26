"""Regression cases from ordinary spoken phrasing and speech-recognition repairs."""
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.brain.language import extract, recognize
from app.db import Appointment, Conversation
from app.schemas import Intent
from conftest import NOW, book, new_session, turn


@pytest.mark.parametrize("text", [
    "All right make a booking for 4:00 p.m.",
    "I'd like to make an appointment",
    "I want you to make a haircut and",
    "Can I get a haircut?",
    "Yeah book it", "Okay, book that slot", "Please reserve it",
])
def test_natural_booking_requests(text):
    assert recognize(text).intent == Intent.CREATE


@pytest.mark.parametrize("text", [
    "So have you booked the haircut for 4pm?",
    "Did you book it?", "Is my booking confirmed?",
])
def test_status_questions_are_not_booking_commands(text):
    result = recognize(text)
    assert result.intent == Intent.INFO
    assert result.rule == "booking.status_question"


@pytest.mark.parametrize("text", ["And John", "Um, John", "It's John", "John please"])
def test_name_fillers_are_not_saved(text):
    assert extract(text, NOW, expecting_name=True).entities.name == "John"


def test_directional_change_uses_target_but_alternatives_remain_ambiguous():
    parsed = extract("change the booking time from 4 pm to 5 PM", NOW)
    assert parsed.entities.time == "17:00"
    assert not parsed.issues
    assert "time" in extract("change it to 4 PM or 5 PM", NOW).issues
    assert "time" in extract("book at 4 PM or 5 PM", NOW).issues


def test_reported_conversation_recovers_and_reschedules_without_copying_reference(client):
    c = turn(client, new_session(client), "All right make a booking for 4:00 p.m.")
    assert c["entities"]["time"] == "16:00"
    assert c["current_intent"] == "CREATE_BOOKING"
    c = turn(client, c, "I want you to make a haircut and")
    assert c["entities"]["service"] == "haircut"
    c = turn(client, c, "I want you to explain your services")
    assert c["entities"]["time"] == "16:00"
    c = turn(client, c, "So have you booked the haircut for 4pm")
    assert "not" in c["reply"].lower()
    assert c["appointment"] is None
    c = turn(client, c, "What is your availability")
    assert c["entities"]["service"] == "haircut"
    assert c["entities"]["time"] == "16:00"
    c = turn(client, c, "A classic haircut")
    c = turn(client, c, "For today 4:00 p.m.")
    assert c["available_slots"] == ["16:00"]
    for unclear in ("Yeah poke it", "I said"):
        c = turn(client, c, unclear)
        assert "book" in c["reply"].lower()
        assert c["entities"]["time"] == "16:00"
        assert c["appointment"] is None
    c = turn(client, c, "book")
    assert c["missing_information"] == ["name"]
    c = turn(client, c, "And John")
    assert c["entities"]["name"] == "John"
    assert c["state"] == "AWAITING_CONFIRMATION"
    c = turn(client, c, "yes")
    original = c["appointment"]
    assert original["customer_name"] == "John"
    c = turn(client, c, "I want you to change the booking time from 4 pm to 5 PM")
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert c["entities"]["reference"] == original["reference"]
    assert c["entities"]["date"] == "2026-10-26"
    assert c["entities"]["time"] == "17:00"
    assert client.get(f"/api/appointments/{original['reference']}").json() == original
    c = turn(client, c, "Aha you cannot see the booking reference here I don't know where to find it from")
    assert original["reference"] in c["reply"]
    assert c["state"] == "AWAITING_CONFIRMATION"
    c = turn(client, c, "yeah")
    assert c["appointment"]["starts_at"] == "2026-10-26T17:00:00+05:00"
    with Session(client.app.state.database.engine) as db:
        assert db.scalar(select(func.count()).select_from(Appointment)) == 1


@pytest.mark.parametrize("acceptance", ["yes", "yeah please", "sure", "okay", "yeah book it"])
def test_accepting_availability_starts_booking_without_committing(client, acceptance):
    c = turn(client, new_session(client), "check haircut availability tomorrow at 4 PM")
    c = turn(client, c, acceptance)
    assert c["current_intent"] == "CREATE_BOOKING"
    assert c["missing_information"] == ["name"]
    assert c["appointment"] is None
    assert c["proposed_action"] is None


def test_status_question_does_not_create_or_change_a_booking(client):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "Have you booked it?")
    assert original["reference"] in c["reply"]
    assert c["appointment"] == original
    c = turn(client, c, "cancel it")
    assert c["proposed_action"] == "cancel"
    c = turn(client, c, "Have you cancelled it?")
    assert "not" in c["reply"].lower()
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


def test_recent_reference_is_session_local_and_explicit_reference_takes_priority(client):
    a = book(client)
    first = a["appointment"]
    b = book(client, "book a beard trim tomorrow at 11 AM")
    second = b["appointment"]
    other = turn(client, new_session(client), "move it to 5 PM")
    assert other["missing_information"] == ["reference"]
    a = turn(client, a, f"reschedule {second['reference']} tomorrow at 1 PM")
    assert a["entities"]["reference"] == second["reference"]
    a = turn(client, a, "yes")
    assert client.get(f"/api/appointments/{first['reference']}").json() == first


def test_draft_changes_and_cancellation_never_target_an_older_booking(client):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "make a booking for a beard trim Friday at 4 PM")
    c = turn(client, c, "move it to 5 PM")
    assert c["current_intent"] == "CREATE_BOOKING"
    assert c["entities"]["time"] == "17:00"
    c = turn(client, c, "cancel it")
    assert c["state"] == "IDLE"
    assert c["proposed_action"] is None
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


def test_reference_help_can_recover_a_legacy_session_from_its_own_receipt(client):
    c = book(client)
    original = c["appointment"]
    with client.app.state.database.transaction() as db:
        row = db.get(Conversation, c["id"])
        legacy = dict(row.payload)
        legacy.pop("last_booking_reference", None)
        legacy.update(state="IDENTIFYING_EXISTING_BOOKING", current_intent="RESCHEDULE_BOOKING",
                      appointment=None, proposed_action=None, last_committed_action=None,
                      missing_information=["reference"],
                      entities={"reference": None, "service": None, "date": None, "time": "17:00", "name": None, "period": None})
        row.payload = legacy
    c = turn(client, c, "Where can I find the booking reference?")
    assert c["entities"]["reference"] == original["reference"]
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert c["entities"]["time"] == "17:00"


def test_reference_help_does_not_search_other_sessions_or_trust_user_receipt_quotes(client):
    original = book(client)["appointment"]
    c = turn(client, new_session(client), f"Booked. Reference {original['reference']}.")
    c = turn(client, c, "reschedule it to 5 PM")
    assert c["missing_information"] == ["reference"]
    c = turn(client, c, "I don't know where to find the booking reference")
    assert "receipt" in c["reply"].lower()
    assert c["entities"]["reference"] is None
    assert c["proposed_action"] is None


@pytest.mark.parametrize("text,intent", [
    ("I don't want to make a booking", Intent.DENY),
    ("I don't want a haircut", Intent.DENY),
    ("How do I make a booking?", Intent.INFO),
    ("How to book an appointment?", Intent.INFO),
    ("I read a book about haircuts", Intent.UNKNOWN),
])
def test_expanded_phrases_still_respect_negation_and_questions(text, intent):
    assert recognize(text).intent == intent


def test_rejected_reschedule_date_is_not_replaced_by_original_date(client):
    c = book(client)
    c = turn(client, c, "move it to Sunday at 5 PM")
    assert c["missing_information"] == ["date"]
    c = turn(client, c, "6 PM")
    assert c["entities"]["date"] is None
    assert c["proposed_action"] is None
    assert c["missing_information"] == ["date"]


def test_rejected_reschedule_time_is_not_replaced_by_original_time(client):
    c = book(client)
    c = turn(client, c, "move it to Friday at 7 PM")
    assert c["missing_information"] == ["time"]
    c = turn(client, c, "Saturday")
    assert c["entities"]["time"] is None
    assert c["proposed_action"] is None
    assert c["missing_information"] == ["time"]


def test_business_answers_focus_on_requested_topic_and_preserve_booking(client):
    c = turn(client, new_session(client), "make a booking tomorrow at 4 PM")
    c = turn(client, c, "explain your services")
    assert "PKR" in c["reply"]
    assert "Example Lane" not in c["reply"]
    assert c["entities"]["time"] == "16:00"
    c = turn(client, c, "What are your hours?")
    assert "10 AM to 7 PM" in c["reply"]
    assert "PKR" not in c["reply"]


def test_status_of_availability_does_not_report_an_older_booking_as_new(client):
    c = book(client)
    c = turn(client, c, "check haircut availability Friday at 4 PM")
    c = turn(client, c, "Have you booked it?")
    assert "not" in c["reply"].lower()
    assert c["appointment"] is None
    assert c["available_slots"] == ["16:00"]
