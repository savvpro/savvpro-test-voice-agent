"""A name supplied with booking details survives independent slot repairs."""
import pytest

from app.brain.language import extract
from conftest import NOW, book, new_session, turn


@pytest.mark.parametrize("text", [
    "You should use Muhammad",
    "You should use the name Muhammad",
    "You can use Muhammad",
    "Could you use Muhammad please",
    "Please, you should use Muhammad",
    "Actually, you should use Muhammad",
])
def test_explicit_spoken_name_instruction(text):
    assert extract(text, NOW, expecting_name=True).entities.name == "Muhammad"


@pytest.mark.parametrize("text", [
    "book a haircut with the name Muhammad Taha on October 28 2026 at 4 PM",
    "make a new booking with the name Muhammad Taha and 28th of October 2026 at 4 PM for a haircut",
    "book a haircut on October 28 2026 at 4 PM under the name Muhammad Taha",
    "book with the name Muhammad Taha for a haircut on October 28 2026 at 4 PM",
    "book a haircut and use the name Muhammad Taha, on October 28 2026 at 4 PM",
])
def test_name_and_calendar_details_can_arrive_in_one_request(text):
    parsed = extract(text, NOW)
    assert parsed.entities.name == "Muhammad Taha"
    assert parsed.entities.date == "2026-10-28"
    assert parsed.entities.time == "16:00"
    assert parsed.entities.service == "haircut"
    assert not parsed.issues


@pytest.mark.parametrize("bad_date", ["428th of October 2026", "31st of November 2026", "2026 0 to 10"])
def test_invalid_date_does_not_erase_an_explicit_name_or_valid_time(bad_date):
    parsed = extract(f"make a new booking with the name Muhammad Taha and {bad_date} at 4 PM", NOW)
    assert parsed.entities.name == "Muhammad Taha"
    assert parsed.entities.time == "16:00"
    assert parsed.entities.date is None
    assert set(parsed.issues) == {"date"}


@pytest.mark.parametrize("text", [
    "book a haircut with the name Muhammad or John tomorrow at 4 PM",
    "book a haircut with the name tomorrow at 4 PM",
    "book a haircut with the name Muhammad and cancel it tomorrow at 4 PM",
    "book a haircut tomorrow at 4 PM",  # Never infer a name from service details.
    "tell me why my name is Muhammad",
    "You should use my previous name",
])
def test_name_grammar_does_not_guess_or_swallow_other_commands(text):
    assert extract(text, NOW, expecting_name=True).entities.name is None


def test_reported_conversation_keeps_name_through_date_repair(client):
    c = turn(client, new_session(client), "All right make a new booking uh with the name Muhammad Taha and 428th of October 2026 at 4:00 p.m.")
    assert c["missing_information"] == ["date"]
    assert c["entities"]["name"] == "Muhammad Taha"
    assert c["entities"]["time"] == "16:00"
    assert c["appointment"] is None
    c = turn(client, c, "28th of October 2026 at 4:00 p.m.")
    assert c["missing_information"] == ["service"]
    c = turn(client, c, "Haircut plus beard")
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert c["entities"]["name"] == "Muhammad Taha"
    assert c["appointment"] is None
    c = turn(client, c, "I just told you the name bro")
    assert "Muhammad Taha" in c["reply"]
    assert c["entities"]["name"] == "Muhammad Taha"
    assert c["appointment"] is None
    c = turn(client, c, "You should use Muhammad")
    assert c["entities"]["name"] == "Muhammad"
    assert c["appointment"] is None
    c = turn(client, c, "Use the name Muhammad Taha")
    assert c["appointment"] is None
    c = turn(client, c, "yes")
    assert c["appointment"]["customer_name"] == "Muhammad Taha"
    assert c["appointment"]["service"] == "combo"
    assert c["appointment"]["starts_at"] == "2026-10-28T16:00:00+05:00"
    stored = client.get(f"/api/appointments/{c['appointment']['reference']}").json()
    assert stored == c["appointment"]


def test_name_reminder_does_not_invent_a_missing_name(client):
    c = turn(client, new_session(client), "book a haircut tomorrow at 4 PM")
    c = turn(client, c, "I just told you the name bro")
    assert c["entities"]["name"] is None
    assert c["missing_information"] == ["name"]
    assert "don't have a name" in c["reply"]
    c = turn(client, c, "You should use Muhammad")
    assert c["entities"]["name"] == "Muhammad"
    assert c["appointment"] is None


def test_new_booking_does_not_inherit_a_previous_customer_name(client):
    c = turn(client, new_session(client), "book a haircut with the name Alex Example tomorrow at 4 PM")
    c = turn(client, c, "yes")
    assert c["appointment"]["customer_name"] == "Alex Example"
    c = turn(client, c, "make a new booking for a haircut on October 28 2026 at 4 PM")
    assert c["missing_information"] == ["name"]
    assert c["entities"]["name"] is None


@pytest.mark.parametrize("has_proposal", [False, True])
def test_multiple_explicit_names_require_clarification(client, has_proposal):
    c = new_session(client)
    if has_proposal:
        c = turn(client, c, "book a haircut tomorrow at 4 PM with the name Alex Example")
        assert c["state"] == "AWAITING_CONFIRMATION"
    c = turn(client, c, "book a haircut tomorrow at 4 PM with the name Muhammad and use the name John")
    assert c["entities"]["name"] is None
    assert c["missing_information"] == ["name"]
    assert c["proposed_action"] is None
    c = turn(client, c, "yes")
    assert c["appointment"] is None


@pytest.mark.parametrize("name", ["Alex Beard", "May Demo", "Anne-Marie O'Neill"])
def test_consumed_name_words_cannot_become_services_or_calendar_dates(name):
    parsed = extract(f"book a haircut with the name {name} on October 28 2026 at 4 PM", NOW)
    assert parsed.entities.name == name
    assert parsed.entities.service == "haircut"
    assert parsed.entities.date == "2026-10-28"
    assert not parsed.issues


def test_explicit_name_survives_a_time_error_and_is_used_after_repair(client):
    c = turn(client, new_session(client), "book a haircut with the name Muhammad Taha tomorrow at around 40")
    assert c["missing_information"] == ["time"]
    assert c["entities"]["name"] == "Muhammad Taha"
    c = turn(client, c, "4 PM")
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert c["entities"]["name"] == "Muhammad Taha"
    assert c["appointment"] is None


def test_negated_name_instruction_clears_an_existing_proposal(client):
    c = turn(client, new_session(client), "book a haircut with the name Alex Example tomorrow at 4 PM")
    assert c["state"] == "AWAITING_CONFIRMATION"
    c = turn(client, c, "book a haircut tomorrow at 4 PM and do not use the name Alex Example")
    assert c["entities"]["name"] is None
    assert c["missing_information"] == ["name"]
    assert c["proposed_action"] is None
    c = turn(client, c, "yes")
    assert c["appointment"] is None


@pytest.mark.parametrize("prefix", ["for the name", "for name", "with the name", "with name"])
def test_name_prepositions_in_a_booking_request(prefix):
    parsed = extract(f"I want you to make a booking for haircut {prefix} Muhammadaha on the on 28th of October 2026 at 4:00 p.m.", NOW)
    assert parsed.entities.name == "Muhammadaha"
    assert parsed.entities.service == "haircut"
    assert parsed.entities.date == "2026-10-28"
    assert parsed.entities.time == "16:00"
    assert not parsed.issues


@pytest.mark.parametrize("prefix", ["for the name", "for name", "with the name", "with name"])
def test_name_prepositions_in_a_separate_answer(prefix):
    parsed = extract(f"{prefix} Muhammad Taha", NOW, expecting_name=True)
    assert parsed.entities.name == "Muhammad Taha"
    assert not parsed.issues


@pytest.mark.parametrize("second_slot_taken", [False, True])
def test_occupied_slot_keeps_name_until_explicit_correction(client, second_slot_taken):
    original = book(client, "book a haircut on October 28 2026 at 4 PM")["appointment"]
    if second_slot_taken:
        book(client, "book a haircut on October 28 2026 at 5 PM")
    c = turn(client, new_session(client), "I want you to make a booking for haircut for the name Muhammadaha on the on 28th of October 2026 at 4:00 p.m.")
    assert c["entities"]["name"] == "Muhammadaha"
    assert c["entities"]["time"] is None
    assert c["missing_information"] == ["time"]
    assert "taken" in c["reply"]
    c = turn(client, c, "Yeah change it to 5:00 p.m.")
    assert c["entities"]["name"] == "Muhammadaha"
    if second_slot_taken:
        assert c["missing_information"] == ["time"]
        c = turn(client, c, "6 PM")
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert "Muhammadaha" in c["reply"]
    assert c["appointment"] is None
    c = turn(client, c, "I already told you the name is Muhammad Taha")
    assert c["entities"]["name"] == "Muhammad Taha"
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert c["appointment"] is None
    c = turn(client, c, "yes")
    assert c["appointment"]["customer_name"] == "Muhammad Taha"
    expected_time = "18:00" if second_slot_taken else "17:00"
    assert c["appointment"]["starts_at"] == f"2026-10-28T{expected_time}:00+05:00"
    assert client.get(f"/api/appointments/{original['reference']}").json() == original
