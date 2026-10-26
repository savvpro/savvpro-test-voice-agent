"""Tests for the slot extractors."""

from datetime import datetime, timedelta

from backend.brain.slots import (
    extract_date, extract_time, extract_party_size,
    extract_phone, extract_name, extract_all,
)


NOW = datetime(2026, 10, 27, 11, 0, 0)  # Tuesday


# ---------------------------------------------------------------------------
# DATE
# ---------------------------------------------------------------------------
class TestExtractDate:
    def test_today(self):
        assert extract_date("today", NOW) == "2026-10-27"
        assert extract_date("I want to book today", NOW) == "2026-10-27"
        assert extract_date("tonight", NOW) == "2026-10-27"

    def test_tomorrow(self):
        assert extract_date("tomorrow", NOW) == "2026-10-28"
        assert extract_date("see you tomorrow", NOW) == "2026-10-28"

    def test_day_after_tomorrow(self):
        assert extract_date("day after tomorrow", NOW) == "2026-10-29"

    def test_in_n_days(self):
        assert extract_date("in 3 days", NOW) == "2026-10-30"
        assert extract_date("in 1 day", NOW) == "2026-10-28"

    def test_weekday_next(self):
        # 2026-10-27 is Tuesday. "Friday" should give 2026-10-30.
        assert extract_date("friday", NOW) == "2026-10-30"
        assert extract_date("this friday", NOW) == "2026-10-30"
        assert extract_date("next friday", NOW) == "2026-10-30"
        assert extract_date("wednesday", NOW) == "2026-10-28"

    def test_weekday_rolls_to_next_week_if_same_day(self):
        # Saying "Tuesday" on a Tuesday should give next Tuesday (7 days later)
        assert extract_date("Tuesday", NOW) == "2026-11-03"

    def test_month_name_day(self):
        assert extract_date("January 5", NOW) == "2027-01-05"
        assert extract_date("Jan 5", NOW) == "2027-01-05"
        assert extract_date("December 25", NOW) == "2026-12-25"
        assert extract_date("5 January", NOW) == "2027-01-05"
        assert extract_date("5th of January", NOW) == "2027-01-05"

    def test_iso_numeric(self):
        assert extract_date("2026-11-15", NOW) == "2026-11-15"
        assert extract_date("11/15", NOW) == "2026-11-15"
        assert extract_date("11/15/2026", NOW) == "2026-11-15"

    def test_past_date_rolls_to_next_year(self):
        # Jan 5 already passed this year (we're in Oct), so should give 2027
        assert extract_date("January 5", NOW) == "2027-01-05"

    def test_none_on_no_match(self):
        assert extract_date("hello there", NOW) is None
        assert extract_date("", NOW) is None
        assert extract_date("see you soon", NOW) is None


# ---------------------------------------------------------------------------
# TIME
# ---------------------------------------------------------------------------
class TestExtractTime:
    def test_am_pm(self):
        assert extract_time("7pm") == "19:00"
        assert extract_time("7 pm") == "19:00"
        assert extract_time("7 p.m.") == "19:00"
        assert extract_time("7am") == "07:00"
        assert extract_time("9am") == "09:00"

    def test_with_minutes(self):
        assert extract_time("7:30pm") == "19:30"
        assert extract_time("7:30 pm") == "19:30"
        assert extract_time("19:30") == "19:30"
        assert extract_time("11:45 am") == "11:45"

    def test_noon_midnight(self):
        assert extract_time("noon") == "12:00"
        assert extract_time("midnight") == "00:00"
        assert extract_time("12pm") == "12:00"
        assert extract_time("12am") == "00:00"

    def test_word_forms(self):
        assert extract_time("half past seven") == "19:30"
        assert extract_time("half past 7") == "19:30"
        assert extract_time("seven thirty") == "19:30"
        assert extract_time("quarter past seven") == "19:15"
        assert extract_time("quarter to eight") == "19:45"

    def test_with_context_words(self):
        assert extract_time("at 7") == "19:00"
        assert extract_time("around 7") == "19:00"
        assert extract_time("at 7 o'clock") == "19:00"
        assert extract_time("7 in the evening") == "19:00"
        assert extract_time("7 tonight") == "19:00"

    def test_24h(self):
        assert extract_time("19:30") == "19:30"
        assert extract_time("00:15") == "00:15"
        assert extract_time("23:45") == "23:45"

    def test_none(self):
        assert extract_time("hello") is None
        assert extract_time("") is None
        assert extract_time("see you later") is None


# ---------------------------------------------------------------------------
# PARTY SIZE
# ---------------------------------------------------------------------------
class TestExtractPartySize:
    def test_digit_forms(self):
        assert extract_party_size("for 4") == 4
        assert extract_party_size("for 4 people") == 4
        assert extract_party_size("4 people") == 4
        assert extract_party_size("party of 4") == 4
        assert extract_party_size("table for 4") == 4
        assert extract_party_size("reservation for 4") == 4
        assert extract_party_size("group of 6") == 6
        assert extract_party_size("4 of us") == 4

    def test_word_forms(self):
        assert extract_party_size("for four") == 4
        assert extract_party_size("table for two") == 2
        assert extract_party_size("party of six") == 6
        assert extract_party_size("a couple") == 2

    def test_solo(self):
        assert extract_party_size("just me") == 1
        assert extract_party_size("for myself") == 1
        assert extract_party_size("by myself") == 1
        assert extract_party_size("alone") == 1
        assert extract_party_size("table for one") == 1

    def test_none(self):
        assert extract_party_size("hello") is None
        assert extract_party_size("") is None
        assert extract_party_size("see you tomorrow") is None


# ---------------------------------------------------------------------------
# PHONE
# ---------------------------------------------------------------------------
class TestExtractPhone:
    def test_common_formats(self):
        assert extract_phone("555-123-4567") == "5551234567"
        assert extract_phone("(555) 123-4567") == "5551234567"
        assert extract_phone("5551234567") == "5551234567"
        assert extract_phone("555.123.4567") == "5551234567"

    def test_with_country_code(self):
        assert extract_phone("+1 555-123-4567") == "5551234567"
        assert extract_phone("1-555-123-4567") == "5551234567"

    def test_in_sentence(self):
        assert extract_phone("my number is 555-123-4567") == "5551234567"

    def test_none(self):
        assert extract_phone("hello") is None
        assert extract_phone("") is None
        assert extract_phone("555") is None  # too short


# ---------------------------------------------------------------------------
# NAME
# ---------------------------------------------------------------------------
class TestExtractName:
    def test_with_marker(self):
        assert extract_name("my name is John") == "John"
        assert extract_name("my name's John") == "John"
        assert extract_name("this is Sarah") == "Sarah"
        assert extract_name("it's under Smith") == "Smith"
        assert extract_name("book under Patel") == "Patel"
        assert extract_name("I'm Mike") == "Mike"
        assert extract_name("I am Mike") == "Mike"

    def test_multi_word_name(self):
        assert extract_name("my name is John Smith") == "John Smith"
        assert extract_name("it's Mary Jane Watson") == "Mary Jane Watson"

    def test_standalone_capitalized(self):
        # When given just a name (state machine only calls this in ASK_NAME)
        assert extract_name("John") == "John"
        assert extract_name("Sarah") == "Sarah"

    def test_none(self):
        assert extract_name("hello") is None
        assert extract_name("") is None
        assert extract_name("book a table") is None


# ---------------------------------------------------------------------------
# extract_all — multi-slot in one utterance
# ---------------------------------------------------------------------------
class TestExtractAll:
    def test_three_slots_one_utterance(self):
        result = extract_all("I want to book tomorrow at 7pm for 4 people", NOW)
        assert result["date"] == "2026-10-28"
        assert result["time"] == "19:00"
        assert result["party_size"] == 4
        assert result["phone"] is None
        assert result["name"] is None

    def test_partial_extraction(self):
        result = extract_all("friday at 8", NOW)
        assert result["date"] == "2026-10-30"
        assert result["time"] == "20:00"
        assert result["party_size"] is None
