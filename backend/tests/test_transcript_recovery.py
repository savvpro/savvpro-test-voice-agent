"""Second real-conversation regression: corrections, time shapes and handoff."""
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.brain.language import extract, recognize
from app.db import Appointment
from app.schemas import Intent
from conftest import NOW, book, new_session, turn


@pytest.mark.parametrize("text,expected", [
    ("5 30 PM", "17:30"),
    ("four 30 p.m.", "16:30"),
    ("at 4 thirty PM", "16:30"),
    ("Change the booking timing from 4 30 PM to 5 30 PM", "17:30"),
    ("tomorrow around 6:30 p.m.", "18:30"),
    ("I already told you it's 4:30 p.m.", "16:30"),
])
def test_transcribed_clock_forms(text, expected):
    parsed = extract(text, NOW)
    assert parsed.entities.time == expected
    assert not parsed.issues


@pytest.mark.parametrize("text", [
    "today at around 40", "today around forty", "at around 430",
    "at 4 60 PM", "around 40 PM", "5 30", "at around five",
])
def test_unclear_time_claim_cannot_be_ignored(text):
    parsed = extract(text, NOW)
    assert "time" in parsed.issues
    assert parsed.entities.time is None


@pytest.mark.parametrize("text,intent", [
    ("I said yes book it", Intent.CREATE),
    ("I said, yes, book it", Intent.CREATE),
    ("Make a new booking for tomorrow around 6:30 p.m.", Intent.CREATE),
    ("make another appointment", Intent.CREATE),
    ("I said yes", Intent.CONFIRM),
    ("Yes do it at 4:30 p.m.", Intent.MODIFY),
    ("I said don't make a new booking", Intent.DENY),
    ("Cancel this booking and make a new booking", Intent.UNKNOWN),
    ("Yes look it", Intent.UNKNOWN),
])
def test_repair_prefix_and_bounded_action_phrases(text, intent):
    assert recognize(text).intent == intent


def test_unclear_availability_time_requests_clarification_not_an_all_day_search(client):
    c = turn(client, new_session(client), "tell me the availability for a haircut")
    c = turn(client, c, "I want you to do it today at around 40")
    assert c["missing_information"] == ["time"]
    assert c["available_slots"] == []
    assert c["entities"]["date"] == "2026-10-26"
    assert c["last_decision"]["matched_rule"] == "entities.ambiguous"


@pytest.mark.parametrize("utterance,expected_intent", [
    ("Yes do it at 4:30 p.m.", "CREATE_BOOKING"),
    ("yes at 4:30 PM", "CREATE_BOOKING"),
    ("at 4:30 PM", "CHECK_AVAILABILITY"),
    ("I already told you it's 4:30 p.m.", "CHECK_AVAILABILITY"),
])
def test_details_after_availability_are_not_discarded(client, utterance, expected_intent):
    c = turn(client, new_session(client), "check haircut availability today")
    c = turn(client, c, utterance)
    assert c["entities"]["time"] == "16:30"
    assert c["current_intent"] == expected_intent
    assert c["appointment"] is None
    assert c["proposed_action"] is None
    if expected_intent == "CREATE_BOOKING":
        assert c["missing_information"] == ["name"]
    else:
        assert c["available_slots"] == ["16:30"]
        c = turn(client, c, "I said yes book it")
        assert c["entities"]["time"] == "16:30"
        assert c["missing_information"] == ["name"]


def test_selected_time_is_rechecked_instead_of_trusting_the_earlier_slot_list(client):
    c = turn(client, new_session(client), "check haircut availability today")
    original = book(client, "book a haircut today at 4:30 PM")["appointment"]
    c = turn(client, c, "Yes do it at 4:30 PM")
    assert c["entities"]["time"] is None
    assert c["proposed_action"] is None
    assert "taken" in c["reply"]
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


def test_yes_with_new_details_requires_review_before_a_write(client):
    c = turn(client, new_session(client), "book a haircut today at 4 PM")
    c = turn(client, c, "John Demo")
    c = turn(client, c, "yes do it at 4:30 PM")
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert c["entities"]["time"] == "16:30"
    assert c["appointment"] is None
    c = turn(client, c, "I said yes")
    assert c["appointment"]["starts_at"] == "2026-10-26T16:30:00+05:00"


def test_complete_second_reported_conversation(client):
    c = new_session(client)
    c = turn(client, c, "All right tell me what's the inability to increase uh reduce our cooldown")
    assert c["appointment"] is None
    c = turn(client, c, "I want you to tell me the availability")
    c = turn(client, c, "Effect")
    assert c["entities"]["service"] is None  # Never guess the garbled service.
    c = turn(client, c, "I said a classic haircut")
    c = turn(client, c, "I want you to do it today at around 40")
    assert c["missing_information"] == ["time"]
    assert not c["available_slots"]
    c = turn(client, c, "Yes do it at 4:30 p.m.")
    assert c["entities"]["time"] == "16:30"
    assert c["missing_information"] == ["name"]
    for unclear in ("Yes look it", "I said yes book it", "Yes", "I already told you it's 4:30 p.m."):
        c = turn(client, c, unclear)
        assert c["entities"]["time"] == "16:30"
        assert c["entities"]["name"] is None
        assert c["missing_information"] == ["name"]
    c = turn(client, c, "John")
    c = turn(client, c, "yes")
    first = c["appointment"]
    assert first["starts_at"] == "2026-10-26T16:30:00+05:00"
    c = turn(client, c, "Change the booking timing from 4 30 PM to 5 30 PM")
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert c["entities"]["time"] == "17:30"
    c = turn(client, c, "5:30 p.m.")
    c = turn(client, c, "yes")
    assert c["appointment"]["starts_at"] == "2026-10-26T17:30:00+05:00"
    c = turn(client, c, "Cancel this booking")
    c = turn(client, c, "yes")
    assert c["appointment"]["status"] == "cancelled"
    c = turn(client, c, "Make a new booking for tomorrow around 6:30 p.m.")
    assert c["current_intent"] == "CREATE_BOOKING"
    assert c["entities"]["date"] == "2026-10-27"
    assert c["entities"]["time"] == "18:30"
    assert c["entities"]["service"] is None
    c = turn(client, c, "Book a haircut for tomorrow at around 6:30 p.m.")
    c = turn(client, c, "John")
    c = turn(client, c, "yes")
    assert c["appointment"]["starts_at"] == "2026-10-27T18:30:00+05:00"
    assert c["appointment"]["reference"] != first["reference"]
    assert client.get(f"/api/appointments/{first['reference']}").json()["status"] == "cancelled"
    with Session(client.app.state.database.engine) as db:
        assert db.scalar(select(func.count()).select_from(Appointment)) == 2


@pytest.mark.parametrize("text", ["I said yes book it", "Yes, book that appointment please", "yes please reserve it"])
def test_explicit_action_affirmative_confirms_only_a_complete_proposal(client, text):
    c = turn(client, new_session(client), "book a haircut today at 4 PM")
    c = turn(client, c, "John Demo")
    c = turn(client, c, text)
    assert c["state"] == "BOOKING_COMPLETE"
    assert c["last_decision"]["matched_rule"] == "commit.confirmed"
    assert c["last_decision"]["intent"] == "CONFIRM"


def test_repaired_cancel_discards_the_draft_instead_of_targeting_an_older_booking(client):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "make a new booking for Friday at 4 PM")
    c = turn(client, c, "I said cancel it")
    assert c["state"] == "IDLE"
    assert c["proposed_action"] is None
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


def test_compound_request_invalidates_pending_authorization(client):
    c = turn(client, new_session(client), "book a haircut today at 4 PM")
    c = turn(client, c, "John Demo")
    c = turn(client, c, "Cancel this booking and make a new booking")
    assert c["proposed_action"] is None
    c = turn(client, c, "yes")
    assert c["appointment"] is None
    assert c["last_decision"]["matched_rule"] == "confirmation.no_proposal"


@pytest.mark.parametrize("text", ["I said John", "I already told you it's John", "Um, I said John"])
def test_repaired_name_answer_does_not_save_the_repair_words(text):
    assert extract(text, NOW, expecting_name=True).entities.name == "John"


def test_new_booking_question_is_information_not_a_creation_command(client):
    c = turn(client, new_session(client), "How do I make a new booking?")
    assert c["current_intent"] == "UNKNOWN"
    assert c["last_decision"]["intent"] == "ASK_BUSINESS_INFO"
    assert "Tell me which service" in c["reply"]
