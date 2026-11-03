"""
Unit tests — Slot extraction (brain/slots.py)

Run:  cd backend && pytest tests/test_slots.py -v
"""

import pytest
from brain.slots import (
    extract_name, extract_doctor, extract_date,
    extract_time, extract_reason, extract_slots,
)


class TestExtractName:
    def test_my_name_is(self):
        assert extract_name("My name is John Smith") == "John Smith"

    def test_im(self):
        assert extract_name("I'm Sara") == "Sara"

    def test_its(self):
        assert extract_name("It's David Lee") == "David Lee"

    def test_plain_two_words(self):
        assert extract_name("John Smith") == "John Smith"

    def test_plain_one_word(self):
        result = extract_name("Sara")
        assert result == "Sara"

    def test_filler_words_stripped(self):
        result = extract_name("um John Smith")
        assert result == "John Smith"

    def test_no_name_in_slot_noise(self):
        # "yes" and "ok" are filler — should not return a name
        assert extract_name("yes") is None
        assert extract_name("ok") is None

    def test_capitalises(self):
        result = extract_name("my name is john smith")
        assert result == "John Smith"


class TestExtractDoctor:
    def test_dr_khan(self):
        assert extract_doctor("I'd like Dr. Khan") == "Dr. Khan"

    def test_doctor_smith(self):
        assert extract_doctor("Doctor Smith please") == "Dr. Smith"

    def test_alias_patel(self):
        assert extract_doctor("Patel") == "Dr. Patel"

    def test_any_preference(self):
        assert extract_doctor("I don't mind") == "any"
        assert extract_doctor("anyone is fine") == "any"
        assert extract_doctor("first available") == "any"

    def test_no_preference(self):
        assert extract_doctor("no preference") == "any"

    def test_unknown_doctor_generic(self):
        result = extract_doctor("Dr. Jones please")
        assert result == "Dr. Jones"

    def test_no_doctor_in_text(self):
        assert extract_doctor("Tuesday at 3pm") is None


class TestExtractTime:
    def test_3pm(self):
        assert extract_time("3pm") == "15:00"

    def test_10am(self):
        assert extract_time("10am") == "10:00"

    def test_3_30pm(self):
        assert extract_time("3:30pm") == "15:30"

    def test_morning(self):
        assert extract_time("morning") == "09:00"

    def test_afternoon(self):
        assert extract_time("afternoon") == "14:00"

    def test_evening(self):
        assert extract_time("evening") == "17:00"

    def test_noon(self):
        assert extract_time("noon") == "12:00"

    def test_24h(self):
        assert extract_time("14:30") == "14:30"

    def test_midnight_12am(self):
        assert extract_time("12am") == "00:00"

    def test_noon_12pm(self):
        assert extract_time("12pm") == "12:00"

    def test_no_time(self):
        assert extract_time("John Smith") is None


class TestExtractDate:
    def test_returns_future_date(self):
        result = extract_date("tomorrow")
        assert result is not None
        assert result > "2026-01-01"       # some future date

    def test_weekday_name(self):
        result = extract_date("Monday")
        assert result is not None          # resolved to nearest future Monday

    def test_no_date_in_text(self):
        assert extract_date("John Smith") is None

    def test_past_date_returns_none(self):
        # "yesterday" is always in the past
        assert extract_date("yesterday") is None

    def test_slash_numeric_formats(self):
        # Formats like 11/2/26 and 2/11/2026 should parse to valid future date
        assert extract_date("11/2/26") == "2026-11-02"
        assert extract_date("2/11/2026") == "2026-11-02"


class TestExtractReason:
    def test_toothache(self):
        assert extract_reason("I have a toothache") == "toothache"

    def test_checkup(self):
        assert extract_reason("just a routine checkup") is not None

    def test_no_reason(self):
        assert extract_reason("John Smith") is None


class TestExtractSlots:
    def test_multi_slot_utterance(self):
        """'Tuesday at 5pm with Dr. Khan' — all three slots extracted at once."""
        slots = extract_slots("Tuesday at 5pm with Dr. Khan")
        assert "date"   in slots
        assert "time"   in slots and slots["time"] == "17:00"
        assert "doctor" in slots and slots["doctor"] == "Dr. Khan"

    def test_name_only(self):
        slots = extract_slots("My name is John Smith")
        assert slots.get("name") == "John Smith"
        assert "doctor" not in slots

    def test_empty_string(self):
        assert extract_slots("") == {}

