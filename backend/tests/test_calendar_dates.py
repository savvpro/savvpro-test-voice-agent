"""Spoken calendar dates must be recognized before numeric time parsing."""
import pytest

from app.brain.language import extract
from conftest import NOW, book, new_session, turn


@pytest.mark.parametrize("text,expected", [
    ("28th of October 2026", "2026-10-28"),
    ("the 28th of October, 2026", "2026-10-28"),
    ("October 28th, 2026", "2026-10-28"),
    ("28 October 2026", "2026-10-28"),
    ("Oct 28 2026", "2026-10-28"),
    ("28th of Oct. 2026", "2026-10-28"),
    ("2026 October 10", "2026-10-10"),
    ("2026 October 28th", "2026-10-28"),
    ("2026 1028", "2026-10-28"),
    ("2026 10 28", "2026-10-28"),
    ("20261028", "2026-10-28"),
    ("twenty eighth of October 2026", "2026-10-28"),
    ("October twenty-eighth 2026", "2026-10-28"),
    ("October 28", "2026-10-28"),
    ("Wednesday November 4 2026", "2026-11-04"),
    ("February 29 2028", "2028-02-29"),
    ("28th of October in 2026", "2026-10-28"),
])
def test_calendar_forms_do_not_become_clock_times(text, expected):
    parsed = extract(text, NOW, expecting_time=True)
    assert parsed.entities.date == expected
    assert parsed.entities.time is None
    assert not parsed.issues


@pytest.mark.parametrize("text", [
    "28th of October 20", "October 28 26", "2026 0 to 10", "2026 102",
    "2026 October", "2026", "31st of November 2026", "February 29 2026",
    "2026 13 28", "2026 0230", "11/12/2026",
    "October 28 2026 or October 29 2026", "Monday October 28 2026",
    "28 10 2026", "10 11 2026", "October 28 twenty twenty seven",
    "Wednesday or November 4 2026",
    "October thirty second 2026", "thirty third of October 2026",
])
def test_incomplete_invalid_and_contradictory_calendar_dates_are_date_questions(text):
    parsed = extract(text, NOW, expecting_time=True)
    assert "date" in parsed.issues
    assert parsed.entities.date is None
    assert parsed.entities.time is None
    assert "time" not in parsed.issues


@pytest.mark.parametrize("text,expected_time", [
    ("at 28th of October 2026 at 4:00 p.m.", "16:00"),
    ("October 28th 2026 at 5 30 PM", "17:30"),
    ("2026 1028 at 4 PM", "16:00"),
    ("2026 October 10 at 5 PM", "17:00"),
])
def test_date_spans_are_removed_without_losing_a_separate_time(text, expected_time):
    parsed = extract(text, NOW)
    assert parsed.entities.date
    assert parsed.entities.time == expected_time
    assert not parsed.issues


def test_malformed_date_keeps_a_separate_valid_time():
    parsed = extract("2026 0 to 10 at 5 PM", NOW, expecting_time=True)
    assert "date" in parsed.issues
    assert "time" not in parsed.issues
    assert parsed.entities.time == "17:00"


def test_main_reported_request_reaches_name_instead_of_asking_for_date_again(client):
    c = turn(client, new_session(client), "All right I want you to cancel that book into and make a new booking which will be around at 28th of October 20")
    assert c["last_decision"]["matched_rule"] == "action.multiple_requests"
    assert c["appointment"] is None
    c = turn(client, c, "Book I want you to make a new booking at 28th of October 2026 at 4:00 p.m. For haircut")
    assert c["entities"]["date"] == "2026-10-28"
    assert c["entities"]["time"] == "16:00"
    assert c["missing_information"] == ["name"]
    c = turn(client, c, "I told you 28th of October 2026 at 4:00 p.m.")
    assert c["missing_information"] == ["name"]
    assert c["entities"]["time"] == "16:00"
    c = turn(client, c, "John Demo")
    c = turn(client, c, "yes")
    assert c["appointment"]["starts_at"] == "2026-10-28T16:00:00+05:00"


def test_reported_date_recovery_preserves_time_and_rejects_a_real_past_date(client):
    c = turn(client, new_session(client), "book a haircut at 4 PM")
    c = turn(client, c, "2026 0 to 10")
    assert c["missing_information"] == ["date"]
    assert c["entities"]["time"] == "16:00"
    assert "AM or PM" not in c["reply"]
    c = turn(client, c, "5:00 p.m.")
    assert c["entities"]["time"] == "17:00"
    assert c["missing_information"] == ["date"]
    c = turn(client, c, "2026 1028")
    assert c["entities"]["date"] == "2026-10-28"
    assert c["missing_information"] == ["name"]
    c = turn(client, c, "2026 October 10")
    assert c["missing_information"] == ["date"]
    assert "2026-10-10" in c["reply"]
    assert "past" in c["reply"].lower()
    assert c["entities"]["time"] == "17:00"
    c = turn(client, c, "28th of October 2026")
    c = turn(client, c, "John Demo")
    c = turn(client, c, "yes")
    assert c["appointment"]["starts_at"] == "2026-10-28T17:00:00+05:00"


def test_date_correction_needs_new_confirmation(client):
    c = turn(client, new_session(client), "book a haircut October 28 2026 at 4 PM")
    c = turn(client, c, "John Demo")
    assert c["state"] == "AWAITING_CONFIRMATION"
    c = turn(client, c, "I told you October 29 2026")
    assert c["entities"]["date"] == "2026-10-29"
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert c["appointment"] is None
    c = turn(client, c, "yes")
    assert c["appointment"]["starts_at"] == "2026-10-29T16:00:00+05:00"


def test_date_correction_rechecks_conflicts(client):
    book(client, "book a haircut October 29 2026 at 4 PM")
    c = turn(client, new_session(client), "book a haircut October 28 2026 at 4 PM")
    c = turn(client, c, "John Demo")
    c = turn(client, c, "I told you October 29 2026")
    assert c["entities"]["time"] is None
    assert c["proposed_action"] is None
    assert c["appointment"] is None
    assert "taken" in c["reply"]


def test_may_as_a_name_or_polite_request_is_not_an_incomplete_calendar_date(client):
    assert extract("my name is May", NOW, expecting_name=True).entities.name == "May"
    assert "date" not in extract("May I book a haircut tomorrow at 4 PM?", NOW).issues
