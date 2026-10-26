from datetime import date, datetime, time

import pytest

from app.brain.responses import (
    TEMPLATES,
    describe_hours,
    describe_prices,
    format_date,
    format_phone,
    format_slots,
    format_time,
    join_words,
    render,
)
from app.services.booking import SERVICES

TODAY = date(2026, 10, 26)

DUMMY = {
    "date": "tomorrow", "time": "9:00 AM", "service": "cleaning", "name": "Alice",
    "phone": "0 3 0 0", "options": "tomorrow at 9:00 AM", "weekday": "Sunday",
    "hours": "Monday to Saturday", "price": 3000, "prices": "x", "services": "x",
    "open": "9:00 AM", "close": "5:00 PM", "ref": "S D C",
}


@pytest.mark.parametrize("action", sorted(TEMPLATES))
def test_every_template_renders_with_dummy_values(action):
    text = render(action, **DUMMY)
    assert text and "{" not in text and "}" not in text


def test_format_time():
    assert format_time(time(9, 0)) == "9:00 AM"
    assert format_time(time(13, 30)) == "1:30 PM"
    assert format_time(time(12, 0)) == "12:00 PM"


def test_format_date_uses_today_and_tomorrow():
    assert format_date(date(2026, 10, 26), TODAY) == "today"
    assert format_date(date(2026, 10, 27), TODAY) == "tomorrow"
    assert format_date(date(2026, 10, 30), TODAY) == "Friday, October 30"
    assert format_date(date(2026, 10, 27)) == "Tuesday, October 27"


def test_join_words():
    assert join_words([]) == ""
    assert join_words(["a"]) == "a"
    assert join_words(["a", "b", "c"]) == "a, b or c"


def test_format_slots_repeats_the_date_only_when_it_changes():
    slots = [datetime(2026, 10, 27, 11, 30), datetime(2026, 10, 27, 12, 0), datetime(2026, 10, 28, 9, 0)]
    assert format_slots(slots, TODAY) == (
        "tomorrow at 11:30 AM, 12:00 PM or Wednesday, October 28 at 9:00 AM"
    )


def test_format_phone_reads_digit_by_digit():
    assert format_phone("0312") == "0 3 1 2"


def test_describe_hours_matches_the_opening_hours_table():
    assert describe_hours() == "Monday to Saturday, 9:00 AM to 5:00 PM; closed on Sunday"


def test_describe_prices_lists_every_service():
    text = describe_prices()
    assert all(name in text for name in SERVICES)
