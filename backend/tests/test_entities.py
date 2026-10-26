"""Tests for entity extraction."""

import pytest
from datetime import date, time, timedelta

from brain.entities import (
    extract_date,
    extract_time,
    extract_party_size,
    extract_name,
    extract_contact,
    extract_all,
)


class TestDateExtraction:
    """Date extraction tests."""

    def test_today(self):
        assert extract_date("today") == date.today()

    def test_tomorrow(self):
        assert extract_date("tomorrow") == date.today() + timedelta(days=1)

    def test_tonight(self):
        assert extract_date("tonight") == date.today()

    def test_day_name(self):
        result = extract_date("friday")
        assert result is not None
        assert result >= date.today()
        assert result.weekday() == 4  # Friday

    def test_next_day(self):
        result = extract_date("next monday")
        assert result is not None
        assert result > date.today()
        assert result.weekday() == 0

    def test_month_day(self):
        result = extract_date("january 15")
        assert result is not None
        assert result.month == 1
        assert result.day == 15

    def test_numeric_date(self):
        result = extract_date("12/25/2026")
        assert result is not None
        assert result.month == 12
        assert result.day == 25

    def test_past_date_returns_none_or_future(self):
        """Past dates should either return None or auto-advance."""
        result = extract_date("01/01/2020")
        # Should return None for clearly past dates
        assert result is None or result >= date.today()


class TestTimeExtraction:
    """Time extraction tests."""

    def test_time_with_period(self):
        assert extract_time("7pm") == time(19, 0)

    def test_time_with_minutes(self):
        assert extract_time("7:30 pm") == time(19, 30)

    def test_time_am(self):
        assert extract_time("11am") == time(11, 0)

    def test_noon(self):
        assert extract_time("noon") == time(12, 0)

    def test_midnight(self):
        assert extract_time("midnight") == time(0, 0)

    def test_time_with_at(self):
        result = extract_time("at 8")
        assert result is not None
        # Ambiguous hour in restaurant context → assume PM
        assert result.hour == 20

    def test_time_24h(self):
        result = extract_time("19:00")
        assert result is not None
        assert result.hour == 19


class TestPartySizeExtraction:
    """Party size extraction tests."""

    def test_for_number(self):
        assert extract_party_size("for 4") == 4

    def test_party_of(self):
        assert extract_party_size("party of 6") == 6

    def test_people(self):
        assert extract_party_size("2 people") == 2

    def test_just_me(self):
        assert extract_party_size("just me") == 1

    def test_word_number(self):
        assert extract_party_size("for two") == 2

    def test_standalone_digit(self):
        assert extract_party_size("4") == 4

    def test_no_party_size(self):
        assert extract_party_size("hello there") is None


class TestNameExtraction:
    """Name extraction tests."""

    def test_my_name_is(self):
        assert extract_name("my name is John") == "John"

    def test_im(self):
        assert extract_name("I'm Sarah") == "Sarah"

    def test_call_me(self):
        assert extract_name("call me Mike") == "Mike"

    def test_short_name_answer(self):
        assert extract_name("John Smith") == "John Smith"

    def test_non_name(self):
        # Should not match common words
        assert extract_name("yes") is None
        assert extract_name("cancel") is None


class TestContactExtraction:
    """Contact (phone) extraction tests."""

    def test_phone_dashes(self):
        assert extract_contact("555-123-4567") == "555-123-4567"

    def test_phone_spaces(self):
        assert extract_contact("555 123 4567") == "555 123 4567"

    def test_phone_dots(self):
        assert extract_contact("555.123.4567") == "555.123.4567"

    def test_no_phone(self):
        assert extract_contact("hello world") is None


class TestExtractAll:
    """Integration test for extract_all."""

    def test_multi_entity(self):
        result = extract_all("Book a table for 4 tomorrow at 7pm")
        assert result["date"] == date.today() + timedelta(days=1)
        assert result["time"] == time(19, 0)
        assert result["party_size"] == 4
