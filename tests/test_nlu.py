from datetime import datetime

import pytest

from backend.domain import PKT, local_slot, validate_slot
from backend.nlu import parse
from tests.conftest import NOW


@pytest.mark.parametrize(
    ("text", "slots"),
    [
        (
            "Book a brake inspection for my SUV tomorrow at 2 PM",
            {
                "service": "brake_inspection",
                "vehicle": "suv",
                "date": "2026-10-27",
                "time": "14:00",
            },
        ),
        (
            "Oil service for my sedan Tuesday at eleven AM",
            {"service": "oil_change", "vehicle": "car", "date": "2026-10-27", "time": "11:00"},
        ),
        (
            "Rotate my tires Wednesday at half past three",
            {"service": "tyre_rotation", "date": "2026-10-28", "time": "15:30"},
        ),
        ("Actually make that Thursday at 11:30", {"date": "2026-10-29", "time": "11:30"}),
        ("2026-10-30 at 16:00", {"date": "2026-10-30", "time": "16:00"}),
        ("October 28 at noon", {"date": "2026-10-28", "time": "12:00"}),
        ("28 October at 9 am", {"date": "2026-10-28", "time": "09:00"}),
        ("day after tomorrow at 2:30 p.m.", {"date": "2026-10-28", "time": "14:30"}),
    ],
)
def test_slots(text: str, slots: dict[str, str]) -> None:
    assert parse(text, NOW).slots == slots


@pytest.mark.parametrize(
    "text",
    [
        "Don't cancel it, reschedule it to Thursday",
        "Do not cancel, move it",
        "Never cancel, move my booking",
    ],
)
def test_negation(text: str) -> None:
    parsed = parse(text, NOW)
    assert parsed.intent == "RESCHEDULE"
    assert "negated_cancel_excluded" in parsed.rules


@pytest.mark.parametrize(
    "text",
    [
        "02/03",
        "February 30",
        "2026-13-01",
        "at 25:00",
        "next week",
        "tomorrow afternoon",
        "oil change and brake inspection",
    ],
)
def test_ambiguity(text: str) -> None:
    assert parse(text, NOW).issue


def test_relative_date_obeys_local_clock() -> None:
    late = datetime(2026, 10, 26, 23, 59, tzinfo=PKT)
    assert parse("tomorrow", late).slots["date"] == "2026-10-27"
    assert parse("next monday", NOW).slots["date"] == "2026-11-02"


@pytest.mark.parametrize(
    ("service", "day", "at", "valid"),
    [
        ("brake_inspection", "2026-10-27", "17:30", False),
        ("brake_inspection", "2026-10-27", "17:00", True),
        ("tyre_rotation", "2026-10-27", "17:30", True),
        ("oil_change", "2026-11-01", "11:00", False),
        ("oil_change", "2026-10-27", "11:15", False),
        ("oil_change", "2026-11-15", "11:00", False),
        ("oil_change", "2026-10-26", "09:30", False),
    ],
)
def test_calendar_rules(service: str, day: str, at: str, valid: bool) -> None:
    assert (validate_slot(service, local_slot(day, at), NOW) is None) == valid
