import datetime as dt

import pytest

from app.brain.datetime_parse import parse_date, parse_daypart, parse_time

TODAY = dt.date(2026, 11, 2)  # Monday


@pytest.mark.parametrize(
    "text,expected",
    [
        ("4 pm", dt.time(16, 0)),
        ("4:30 PM", dt.time(16, 30)),
        ("four thirty pm", dt.time(16, 30)),
        ("half past four", dt.time(16, 30)),
        ("quarter to five", dt.time(16, 45)),
        ("quarter past 10", dt.time(10, 15)),
        ("at 4", dt.time(16, 0)),  # clinic hours: bare 1-6 means PM
        ("around 10", dt.time(10, 0)),
        ("noon", dt.time(12, 0)),
        ("16:00", dt.time(16, 0)),
        ("9 am", dt.time(9, 0)),
        ("4 in the afternoon", dt.time(16, 0)),
        ("ten o'clock", dt.time(10, 0)),
    ],
)
def test_parse_time(text, expected):
    assert parse_time(text).value == expected


def test_bare_number_only_counts_as_time_when_a_time_is_expected():
    assert parse_time("4") is None
    assert parse_time("4", expecting=True).value == dt.time(16, 0)


def test_dates_are_not_mistaken_for_times():
    assert parse_time("on the 15th") is None
    assert parse_time("15 november") is None
    assert parse_time("the 5th of december", expecting=True) is None


def test_assumed_flag():
    assert parse_time("at 4").assumed
    assert not parse_time("4 pm").assumed


@pytest.mark.parametrize(
    "text,expected",
    [
        ("tomorrow", dt.date(2026, 11, 3)),
        ("day after tomorrow", dt.date(2026, 11, 4)),
        ("today", TODAY),
        ("friday", dt.date(2026, 11, 6)),
        ("monday", dt.date(2026, 11, 9)),  # strictly after today
        ("next monday", dt.date(2026, 11, 9)),
        ("next tuesday", dt.date(2026, 11, 10)),
        ("15 november", dt.date(2026, 11, 15)),
        ("november 15th", dt.date(2026, 11, 15)),
        ("the 15th", dt.date(2026, 11, 15)),
        ("the 1st", dt.date(2026, 12, 1)),  # already passed this month
        ("5/11", dt.date(2026, 11, 5)),  # day/month
        ("in three days", dt.date(2026, 11, 5)),
        ("in 2 weeks", dt.date(2026, 11, 16)),
        ("5 october", dt.date(2026, 10, 5)),  # recent past month stays in this year (policy rejects it)
    ],
)
def test_parse_date(text, expected):
    assert parse_date(text, TODAY).day == expected


def test_year_rolls_over_for_months_far_in_the_past():
    assert parse_date("5 january", dt.date(2026, 12, 20)).day == dt.date(2027, 1, 5)
    assert parse_date("5 january", TODAY).day == dt.date(2027, 1, 5)


def test_vague_dates():
    result = parse_date("sometime next week", TODAY)
    assert result.day is None and result.vague


def test_impossible_date_is_ignored():
    assert parse_date("30 february", TODAY).day is None


def test_bare_day_number_when_a_day_is_expected():
    assert parse_date("20", TODAY, expecting=True).day == dt.date(2026, 11, 20)
    assert parse_date("20", TODAY) is None


def test_nothing_found():
    assert parse_date("hello there", TODAY) is None


@pytest.mark.parametrize(
    "text,expected",
    [("in the morning", "morning"), ("this afternoon", "afternoon"), ("evening please", "evening"), ("tonight", None)],
)
def test_parse_daypart(text, expected):
    assert parse_daypart(text) == expected
