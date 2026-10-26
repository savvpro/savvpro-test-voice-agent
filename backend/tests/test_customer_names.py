"""Names are slot values; instruction words are never part of that value."""
import pytest

from app.brain.language import extract
from conftest import NOW, new_session, turn


@pytest.mark.parametrize("text,expected", [
    ("Use name Taha", "Taha"),
    ("Use the name Taha", "Taha"),
    ("Please use the name Taha Ahmed", "Taha Ahmed"),
    ("Could you use the name Taha?", "Taha"),
    ("I want you to use name Taha", "Taha"),
    ("Use Taha", "Taha"),
    ("Put it under Taha", "Taha"),
    ("Put the booking under the name Taha", "Taha"),
    ("Under Taha, please", "Taha"),
    ("The name is Taha", "Taha"),
    ("My name is Taha", "Taha"),
    ("Call me Taha please", "Taha"),
    ("I'm Taha", "Taha"),
    ("It's Taha", "Taha"),
    ("I told you, use name Taha", "Taha"),
    ("Use name José López", "José López"),
    ("Use the name Anne-Marie O'Neill", "Anne-Marie O'Neill"),
    ("Taha Ahmed", "Taha Ahmed"),
])
def test_customer_name_excludes_the_request_wrapper(text, expected):
    result = extract(text, NOW, expecting_name=True)
    assert result.entities.name == expected
    assert not result.issues


@pytest.mark.parametrize("text", [
    "use name", "use the name", "put it under", "use my previous name",
    "Use name Taha or John", "Use name Taha and cancel it", "Use another name",
    "Can you change it", "Use a discount", "yes", "no", "I don't know",
])
def test_missing_or_unrelated_name_commands_are_not_saved_as_names(text):
    assert extract(text, NOW, expecting_name=True).entities.name is None


def test_actual_reported_conversation_persists_only_taha(client):
    c = turn(client, new_session(client), "I want to make an appointment for a haircut at 28th of October 2026 at 3 pm")
    assert c["missing_information"] == ["name"]
    c = turn(client, c, "Use name Taha")
    assert c["entities"]["name"] == "Taha"
    assert c["last_decision"]["extracted_entities"]["name"] == "Taha"
    assert "Use Name" not in c["reply"]
    assert c["appointment"] is None
    c = turn(client, c, "yes")
    assert c["appointment"]["customer_name"] == "Taha"
    stored = client.get(f"/api/appointments/{c['appointment']['reference']}").json()
    assert stored["customer_name"] == "Taha"


def test_explicit_name_correction_updates_proposal_and_requires_confirmation(client):
    c = turn(client, new_session(client), "book a haircut tomorrow at 3 PM")
    c = turn(client, c, "Alex Demo")
    c = turn(client, c, "Actually, please use the name Taha")
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert c["entities"]["name"] == "Taha"
    assert c["appointment"] is None
    c = turn(client, c, "yes")
    assert c["appointment"]["customer_name"] == "Taha"
