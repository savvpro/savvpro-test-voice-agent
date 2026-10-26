"""Unit tests for deterministic slot/intent parsing."""

from datetime import date

from app.engine.parser import extract_date, extract_party, extract_time, parse_utterance


TODAY = date(2026, 10, 26)  # Monday


def test_time_pm():
    assert extract_time("7 pm") == "19:00"
    assert extract_time("7:30 PM") == "19:30"
    assert extract_time("at 5") == "17:00"
    assert extract_time("noon") == "12:00"


def test_date_relative():
    assert extract_date("tomorrow", today=TODAY) == "2026-10-27"
    assert extract_date("today", today=TODAY) == "2026-10-26"
    assert extract_date("Friday", today=TODAY) == "2026-10-30"
    assert extract_date("next Monday", today=TODAY) == "2026-11-02"


def test_party():
    assert extract_party("party of 4") == 4
    assert extract_party("for 6 people") == 6
    assert extract_party("8") == 8


def test_intent_cancel():
    assert parse_utterance("never mind, cancel").intent == "cancel"


def test_intent_provide_bundle():
    r = parse_utterance("tomorrow at 7pm for 4", today=TODAY)
    assert r.intent == "provide_info"
    assert r.date == "2026-10-27"
    assert r.time == "19:00"
    assert r.party_size == 4


def test_unclear():
    assert parse_utterance("asdf qwer").intent == "unclear"
