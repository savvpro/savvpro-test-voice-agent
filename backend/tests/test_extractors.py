from datetime import date, time

import pytest

from app.brain.extractors import (
    detect_choice,
    detect_date,
    detect_name,
    detect_phone,
    detect_relation,
    detect_time,
    to_24h,
)
from app.brain.parser import parse

TODAY = date(2026, 10, 26)  # a Monday


@pytest.mark.parametrize(
    "hour, am_pm, expected",
    [
        (5, None, 17), (9, None, 9), (11, None, 11), (12, None, 12),
        (5, "pm", 17), (11, "am", 11), (12, "am", 0), (12, "pm", 12),
        (17, None, 17),
    ],
)
def test_to_24h(hour, am_pm, expected):
    assert to_24h(hour, am_pm) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("tomorrow at five", time(17, 0)),
        ("5pm", time(17, 0)),
        ("5 pm", time(17, 0)),
        ("I will be there at 11am", time(11, 0)),
        ("at 9", time(9, 0)),
        ("at 12", time(12, 0)),
        ("half past four", time(16, 30)),
        ("quarter to five", time(16, 45)),
        ("quarter past ten", time(10, 15)),
        ("5:30", time(17, 30)),
        ("9:30 am", time(9, 30)),
        ("17:30", time(17, 30)),
        ("2 o'clock", time(14, 0)),
        ("actually make it 1pm", time(13, 0)),
        ("I'll be there at 5 P.M.", time(17, 0)),
        ("noon", time(12, 0)),
        ("can you make it 8k", None),
        ("on 27 October 2026", None),
        ("03123456789", None),
        ("her age is 47", None),
        ("hello", None),
    ],
)
def test_detect_time(text, expected):
    assert detect_time(text) == expected


def test_bare_number_is_a_time_only_when_a_time_was_asked_for():
    assert detect_time("5") is None
    assert detect_time("5", expecting="time") == time(17, 0)
    assert detect_time("eleven", expecting="time") == time(11, 0)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("tomorrow", date(2026, 10, 27)),
        ("day after tomorrow", date(2026, 10, 28)),
        ("today", date(2026, 10, 26)),
        ("what is your time on saturday", date(2026, 10, 31)),
        ("next friday", date(2026, 10, 30)),
        ("on monday", date(2026, 11, 2)),  # today is Monday: next Monday
        ("27 october", date(2026, 10, 27)),
        ("27th of October", date(2026, 10, 27)),
        ("october 27", date(2026, 10, 27)),
        ("I want an appointment on 27 October 2026", date(2026, 10, 27)),
        ("3 January", date(2027, 1, 3)),  # already passed this year
        ("31 february", None),
        ("hello", None),
        ("at five pm", None),
    ],
)
def test_detect_date(text, expected):
    assert detect_date(text, TODAY) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("my phone number is 03123456789", "03123456789"),
        ("0 3 1 2 3 4 5 6 7 8 9", "03123456789"),
        ("0312 345 6789", "03123456789"),
        ("0312-3456789", "03123456789"),
        ("plus 92 300 1234567", "923001234567"),
        ("zero three one two three four five six seven eight nine", "03123456789"),
        ("1234567890", "1234567890"),
        ("at 11 am tomorrow", None),
        ("on 27 10 2026", None),
        ("12345", None),
        ("1234567890123456", None),
    ],
)
def test_detect_phone(text, expected):
    assert detect_phone(text) == expected


@pytest.mark.parametrize(
    "text, expecting, expected",
    [
        ("her name is alice and her age is 47", None, "Alice"),
        ("my name is Bob", None, "Bob"),
        ("Hello my name is Bob and what are your timings", None, "Bob"),
        ("this is Sara Khan", None, "Sara Khan"),
        ("Alice", "name", "Alice"),
        ("Alice Khan", "name", "Alice Khan"),
        ("it's for my father Bob", "name", "Bob"),
        ("its bob", "name", "Bob"),
        ("Alice", None, None),                      # a bare word is not a name unless we asked
        ("what are your fees", "name", None),
        ("no", "name", None),
        ("tomorrow at five", "name", None),
        ("I am in pain", None, None),
        ("I'm fine", None, None),
        ("this is urgent", None, None),
    ],
)
def test_detect_name(text, expecting, expected):
    assert detect_name(text, expecting) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("the second one", 2), ("first", 1), ("the third please", 3),
        ("option 2", 2), ("sounds good", None), ("tomorrow", None),
    ],
)
def test_detect_choice(text, expected):
    assert detect_choice(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("it's for my father", "father"),
        ("I want to extract a tooth of my mother", "mother"),
        ("her name is alice", None),
        ("actually it is for my mom", "mother"),
        ("hello", None),
    ],
)
def test_detect_relation(text, expected):
    assert detect_relation(text) == expected


def test_parse_collects_everything_in_one_sentence():
    result = parse("I need a cleaning tomorrow at five", TODAY)
    assert result.service == "cleaning"
    assert result.appt_date == date(2026, 10, 27)
    assert result.appt_time == time(17, 0)
    assert result.name is None and result.phone is None


def test_parse_side_question_with_an_answer():
    result = parse("her name is alice and what is your clinic time", TODAY)
    assert result.name == "Alice"
    assert "ask_hours" in result.intents


def test_parse_money_is_not_a_time():
    result = parse("can you make it 8k", TODAY)
    assert result.appt_time is None
    assert "ask_discount" in result.intents
