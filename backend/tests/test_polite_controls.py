"""Natural back-outs and closing phrases must never authorize calendar writes."""
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.brain.language import recognize
from app.db import Appointment
from app.schemas import Intent
from conftest import book, new_session, proposal, turn


@pytest.mark.parametrize("text", [
    "Never mind don't do it revert the change",
    "Never mind, don't do it; revert the change",
    "please revert the change",
    "don't do it",
    "do not apply that change",
    "no please discard the proposal",
    "keep my original appointment",
    "forget it and undo this change thanks",
])
def test_natural_back_out_discards_only_the_proposal(client, text):
    assert recognize(text).intent == Intent.DENY
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "reschedule it to Friday at 5 PM")
    c = turn(client, c, text)
    assert c["state"] == "IDLE"
    assert c["proposed_action"] is None
    assert c["appointment"] == original
    c = turn(client, c, "yes")
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


@pytest.mark.parametrize("text", [
    "Nothing thank you so much", "nothing else thanks", "that's all thank you",
    "thank you that's it", "I'm done thanks", "no more thank you",
    "bye thank you", "end the conversation please",
])
def test_polite_closing_ends_without_applying_a_pending_change(client, text):
    assert recognize(text).intent == Intent.END
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "reschedule it to 5 PM")
    c = turn(client, c, text)
    assert c["state"] == "COMPLETED"
    assert c["proposed_action"] is None
    assert "goodbye" in c["reply"].lower()
    c = turn(client, c, "yes")
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


@pytest.mark.parametrize("text", ["thanks", "Thank you so much", "thanks a lot", "thank you very much"])
def test_thanks_acknowledges_without_ending_or_confirming_a_proposal(client, text):
    c = proposal(client)
    entities = c["entities"]
    c = turn(client, c, text)
    assert "welcome" in c["reply"].lower()
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert c["entities"] == entities
    assert c["appointment"] is None
    with Session(client.app.state.database.engine) as db:
        assert db.scalar(select(func.count()).select_from(Appointment)) == 0


@pytest.mark.parametrize("text", [
    "No, I meant Friday at 5 PM",
    "never mind the price, book a haircut tomorrow at 3 PM",
    "nothing before 5 PM",
    "thanks but change it to Friday",
    "do not change my name to Nothing",
])
def test_control_keywords_inside_longer_requests_are_not_false_closings(text):
    assert recognize(text).intent not in (Intent.END, Intent.CONFIRM)


def test_rejecting_an_already_discarded_request_is_honest_and_keeps_saved_receipt(client):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "no")
    assert "no pending request" in c["reply"].lower()
    assert c["appointment"] == original
    assert c["proposed_action"] is None


@pytest.mark.parametrize("pending", ["create", "cancel"])
def test_compound_back_out_cannot_create_or_cancel_an_appointment(client, pending):
    c = book(client)
    original = c["appointment"]
    if pending == "create":
        c = turn(client, c, "book a beard trim Friday at 3 PM with the name Jordan Demo")
    else:
        c = turn(client, c, "cancel my confirmed appointment")
    c = turn(client, c, "Never mind don't do it revert the change")
    c = turn(client, c, "yes")
    assert client.get(f"/api/appointments/{original['reference']}").json() == original
    with Session(client.app.state.database.engine) as db:
        assert db.scalar(select(func.count()).select_from(Appointment)) == 1


def test_reported_beard_booking_reschedule_back_out_and_polite_goodbye(client):
    c = turn(client, new_session(client), "All right I want you to book a beard cut on like 15th of December 2026 at 4:00 p.m.")
    assert c["missing_information"] == ["name"]
    c = turn(client, c, "Uh use the name Taha")
    assert c["entities"]["name"] == "Taha"
    c = turn(client, c, "yes")
    original = c["appointment"]
    assert original["starts_at"] == "2026-12-15T16:00:00+05:00"
    c = turn(client, c, "All right I want you to change the timing for this appointment")
    assert c["missing_information"] == ["time"]
    for text in (
        "Change diamond from 4:00 p.m. To 5:00 p.m.",
        "They scheduled that appointment from 4:00 p.m. To 5:00 p.m.",
    ):
        c = turn(client, c, text)
        assert c["proposed_action"] == "reschedule"
        assert c["entities"]["time"] == "17:00"
        assert client.get(f"/api/appointments/{original['reference']}").json() == original
    c = turn(client, c, "And rescheduled the appointment")
    assert "new date or time" in c["reply"].lower()
    assert c["proposed_action"] is None
    c = turn(client, c, "I said reschedule the appointment from 4 pm to 5 PM")
    assert c["proposed_action"] == "reschedule"
    c = turn(client, c, "Never mind don't do it revert the change")
    assert c["proposed_action"] is None
    assert c["appointment"] == original
    c = turn(client, c, "No")
    assert "no pending request" in c["reply"].lower()
    c = turn(client, c, "Nothing thank you so much")
    assert c["state"] == "COMPLETED"
    assert "goodbye" in c["reply"].lower()
    assert client.get(f"/api/appointments/{original['reference']}").json() == original
    with Session(client.app.state.database.engine) as db:
        assert db.scalar(select(func.count()).select_from(Appointment)) == 1
