"""Operation targets and rejected fields stay explicit across caller repairs."""
import pytest

from conftest import book, turn


@pytest.mark.parametrize("text", [
    "cancel that change", "discard the change", "undo this reschedule",
    "forget the proposal", "please cancel this change",
])
def test_discarding_a_reschedule_never_cancels_the_appointment(client, text):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "reschedule it to Friday at 4 PM")
    c = turn(client, c, text)
    assert c["proposed_action"] is None
    c = turn(client, c, "yes")
    assert c["last_committed_action"] is None
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


@pytest.mark.parametrize("text", [
    "cancel", "cancel it", "cancel this booking", "cancel that appointment",
    "cancel the new booking", "discard the draft",
])
def test_cancelling_a_new_draft_does_not_target_an_older_booking(client, text):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "book a beard trim Friday at 3 PM")
    c = turn(client, c, "Jordan Demo")
    c = turn(client, c, text)
    assert c["proposed_action"] is None
    assert c["state"] == "IDLE"
    c = turn(client, c, "yes")
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


def test_ambiguous_pronoun_during_reschedule_requires_an_explicit_target(client):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "reschedule it to Friday at 4 PM")
    c = turn(client, c, "cancel it")
    assert c["proposed_action"] is None
    assert "discard" in c["reply"].lower()
    assert "confirmed appointment" in c["reply"].lower()
    c = turn(client, c, "yes")
    assert client.get(f"/api/appointments/{original['reference']}").json() == original
    c = turn(client, c, "cancel my confirmed appointment")
    assert c["proposed_action"] == "cancel"
    c = turn(client, c, "yes")
    assert c["appointment"]["status"] == "cancelled"


def test_explicit_reference_can_cancel_a_saved_booking_while_a_draft_exists(client):
    c = book(client)
    reference = c["appointment"]["reference"]
    c = turn(client, c, "book a beard trim Friday at 3 PM")
    c = turn(client, c, f"cancel {reference}")
    assert c["proposed_action"] == "cancel"
    assert c["entities"]["reference"] == reference
    c = turn(client, c, "yes")
    assert c["appointment"]["status"] == "cancelled"


@pytest.mark.parametrize("first,second,field", [
    ("5 PM", "October 30 2026", "date"),
    ("October 30 2026", "5 PM", "time"),
])
def test_multiple_rejected_fields_must_each_be_repaired(client, first, second, field):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "reschedule it to 31st of November 2026 at around 40")
    assert set(c["rejected_fields"]) == {"date", "time"}
    c = turn(client, c, first)
    assert c["entities"][field] is None
    assert field in c["rejected_fields"]
    assert c["proposed_action"] is None
    # An unrelated new issue must not erase the outstanding rejection.
    c = turn(client, c, "make it a massage")
    assert field in c["rejected_fields"]
    c = turn(client, c, "haircut")
    c = turn(client, c, second)
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert c["rejected_fields"] == []
    assert client.get(f"/api/appointments/{original['reference']}").json() == original
    c = turn(client, c, "yes")
    assert c["appointment"]["starts_at"] == "2026-10-30T17:00:00+05:00"


@pytest.mark.parametrize("text", ["don't change my booking to 5 PM", "never move my appointment"])
def test_negated_appointment_changes_discard_the_proposal(client, text):
    c = book(client)
    original = c["appointment"]
    c = turn(client, c, "reschedule it to Friday at 4 PM")
    c = turn(client, c, text)
    assert c["proposed_action"] is None
    c = turn(client, c, "yes")
    assert client.get(f"/api/appointments/{original['reference']}").json() == original
