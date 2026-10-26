"""Contrast sets test meaning changes, not only known transcript spellings."""
import pytest

from app.brain.language import extract, recognize
from app.schemas import Intent
from conftest import NOW, new_session, turn


@pytest.mark.parametrize("text,service", [
    ("haircut without a beard trim", "haircut"),
    ("just a haircut, no beard", "haircut"),
    ("haircut and not a beard trim", "haircut"),
    ("beard trim without a haircut", "beard"),
    ("not a haircut, just a beard trim", "beard"),
    ("haircut rather than beard trim", "haircut"),
    ("haircut instead of beard trim", "haircut"),
    ("hair and beard", "combo"),
    ("haircut plus beard", "combo"),
    ("haircut without a massage", "haircut"),
])
def test_service_inclusion_and_exclusion(text, service):
    parsed = extract(text, NOW)
    assert parsed.entities.service == service
    assert "service" not in parsed.issues


@pytest.mark.parametrize("text", [
    "no haircut and no beard", "haircut or beard", "haircut and no haircut",
    "haircut plus massage", "not both",
])
def test_service_ambiguity_needs_a_positive_single_choice(text):
    parsed = extract(text, NOW)
    assert parsed.entities.service is None
    assert "service" in parsed.issues


@pytest.mark.parametrize("text,time", [
    ("quarter to five PM", "16:45"),
    ("quarter to 1 PM", "12:45"),
    ("quarter to twelve PM", "11:45"),
    ("quarter to twelve AM", "23:45"),
    ("quarter past five PM", "17:15"),
    ("half past five PM", "17:30"),
])
def test_complete_supported_clock_expressions(text, time):
    parsed = extract(text, NOW)
    assert parsed.entities.time == time
    assert not parsed.issues


@pytest.mark.parametrize("text", [
    "twenty to five PM", "ten minutes past five PM", "half to five PM",
    "a little after five PM", "just before five PM", "between four and five PM",
    "not at five PM", "anything but 5 PM",
])
def test_unhandled_or_excluded_times_cannot_collapse_to_the_last_hour(text):
    parsed = extract(text, NOW)
    assert parsed.entities.time is None
    assert "time" in parsed.issues


@pytest.mark.parametrize("text", [
    "not tomorrow", "not on Friday", "except October 28 2026",
    "anything but 2026-10-28", "not tomorrow, Friday",
])
def test_negated_dates_need_an_unambiguous_replacement(text):
    parsed = extract(text, NOW)
    assert parsed.entities.date is None
    assert "date" in parsed.issues


@pytest.mark.parametrize("prefix", [
    "Can you fit me in for", "Could you squeeze me in for", "I need",
    "I'd like", "Please book", "Can I get",
])
@pytest.mark.parametrize("service,expected", [("a haircut", "haircut"), ("a hair and beard appointment", "combo")])
def test_request_families_support_both_single_and_combined_services(client, prefix, service, expected):
    text = f"{prefix} {service} tomorrow at 4 PM"
    assert recognize(text).intent == Intent.CREATE
    c = turn(client, new_session(client), text)
    assert c["entities"]["service"] == expected
    assert c["entities"]["date"] == "2026-10-27"
    assert c["entities"]["time"] == "16:00"
    assert c["missing_information"] == ["name"]


def test_excluded_service_and_clock_offset_are_correct_at_persistence(client):
    c = turn(client, new_session(client), "book a haircut without a beard trim tomorrow at quarter to five PM with the name Alex Example")
    assert c["proposed_action"] == "create"
    assert c["appointment"] is None
    c = turn(client, c, "yes")
    assert c["appointment"]["service"] == "haircut"
    assert c["appointment"]["starts_at"] == "2026-10-27T16:45:00+05:00"


def test_negated_date_clears_old_date_and_requires_fresh_review(client):
    c = turn(client, new_session(client), "book a haircut tomorrow at 4 PM with the name Alex Example")
    c = turn(client, c, "yes please but not tomorrow")
    assert c["entities"]["date"] is None
    assert c["proposed_action"] is None
    c = turn(client, c, "yes")
    assert c["appointment"] is None
    c = turn(client, c, "Friday")
    assert c["state"] == "AWAITING_CONFIRMATION"
    assert c["appointment"] is None


def test_bounded_day_offsets_are_consumed_before_times():
    parsed = extract("in two days at 4 PM", NOW, expecting_time=True)
    assert parsed.entities.date == "2026-10-28"
    assert parsed.entities.time == "16:00"
    assert not parsed.issues
