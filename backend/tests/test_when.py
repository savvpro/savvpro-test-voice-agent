from datetime import date, time

import pytest

from app.nlu.normalize import normalize
from app.nlu.when import find_date, find_part_of_day, find_time

TODAY = date(2026, 10, 26)  # a Monday


@pytest.mark.parametrize(
    "text, expected",
    [
        ("today", date(2026, 10, 26)),
        ("tomorrow", date(2026, 10, 27)),
        ("day after tomorrow", date(2026, 10, 28)),
        ("in 3 days", date(2026, 10, 29)),
        ("friday", date(2026, 10, 30)),
        ("monday", date(2026, 11, 2)),  # said on a Monday: next week's
        ("next tuesday", date(2026, 11, 3)),  # said on a Monday: next week's
        ("next week", date(2026, 11, 2)),
        ("november 4", date(2026, 11, 4)),
        ("the 4th of november", date(2026, 11, 4)),
        ("11/04", date(2026, 11, 4)),
        ("january 5", date(2027, 1, 5)),  # already past this year
        ("the 30th", date(2026, 10, 30)),
        ("the 3rd", date(2026, 11, 3)),
        ("i'd like a cleaning", None),
    ],
)
def test_find_date(text, expected):
    assert find_date(normalize(text), TODAY) == expected


@pytest.mark.parametrize(
    "text, expected, explicit",
    [
        ("at 3 pm", time(15), True),
        ("10:30 am", time(10, 30), True),
        ("three thirty", time(3, 30), False),
        ("noon", time(12), True),
        ("half past two", time(2, 30), False),
        ("quarter to ten", time(9, 45), False),
        ("at 4 in the afternoon", time(16), True),
        ("9 o'clock", time(9), False),
        ("actually, make it 4", time(4), False),
        ("can you change it to 2", time(2), False),
        ("make that 10 am", time(10), True),
        ("4 instead", time(4), False),
    ],
)
def test_find_time(text, expected, explicit):
    found = find_time(normalize(text))
    assert found is not None
    assert found.value == expected
    assert found.explicit_meridiem is explicit


@pytest.mark.parametrize("text", ["my number is 555 123 4567", "it's 135 567454 2132"])
def test_no_time_or_date_in_a_phone_number(text):
    assert find_time(normalize(text)) is None
    assert find_date(normalize(text), TODAY) is None


@pytest.mark.parametrize("text, part", [("in the morning", "morning"), ("sometime in the afternoon", "afternoon"), ("whenever", None)])
def test_part_of_day(text, part):
    assert find_part_of_day(normalize(text)) == part
