"""Comprehensive tests for the intent parser."""

import pytest
from datetime import datetime

from app.brain.parser import IntentParser, ParseResult
from app.brain.states import Intent

# Use a fixed reference date for deterministic tests: Wednesday 2025-01-15
REF = datetime(2025, 1, 15, 10, 0, 0)
parser = IntentParser()


def p(text: str) -> ParseResult:
    """Shortcut to parse with the fixed reference date."""
    return parser.parse(text, reference_date=REF)


# ===================================================================
# Intent detection
# ===================================================================

class TestIntentDetection:

    def test_greeting_hi(self):
        assert p("hi").intent == Intent.GREETING

    def test_greeting_hello(self):
        assert p("hello there").intent == Intent.GREETING

    def test_greeting_good_morning(self):
        assert p("good morning").intent == Intent.GREETING

    def test_greeting_hey(self):
        assert p("hey").intent == Intent.GREETING

    def test_confirm_yes(self):
        assert p("yes").intent == Intent.CONFIRM

    def test_confirm_sure(self):
        assert p("sure").intent == Intent.CONFIRM

    def test_confirm_sounds_good(self):
        assert p("sounds good").intent == Intent.CONFIRM

    def test_confirm_book_it(self):
        assert p("book it").intent == Intent.CONFIRM

    def test_deny_no(self):
        assert p("no").intent == Intent.DENY

    def test_deny_nope(self):
        assert p("nope").intent == Intent.DENY

    def test_deny_wrong(self):
        assert p("that's wrong").intent == Intent.DENY

    def test_cancel_cancel(self):
        assert p("cancel").intent == Intent.CANCEL

    def test_cancel_bye(self):
        assert p("bye").intent == Intent.CANCEL

    def test_cancel_nevermind(self):
        assert p("never mind").intent == Intent.CANCEL

    def test_restart_start_over(self):
        assert p("start over").intent == Intent.RESTART

    def test_restart_new_reservation(self):
        assert p("new reservation").intent == Intent.RESTART

    def test_restart_from_the_beginning(self):
        assert p("from the beginning").intent == Intent.RESTART

    def test_help(self):
        assert p("help").intent == Intent.HELP

    def test_help_what_can_you_do(self):
        assert p("what can you do").intent == Intent.HELP

    def test_change_date(self):
        assert p("change the date").intent == Intent.CHANGE_DATE

    def test_change_time(self):
        assert p("change the time").intent == Intent.CHANGE_TIME

    def test_different_day(self):
        assert p("different day").intent == Intent.CHANGE_DATE

    def test_change_party_size(self):
        assert p("change the number of people").intent == Intent.CHANGE_PARTY_SIZE

    def test_more_people(self):
        assert p("more people").intent == Intent.CHANGE_PARTY_SIZE

    def test_unknown_gibberish(self):
        assert p("asdfghjkl").intent == Intent.UNKNOWN

    def test_empty_string(self):
        assert p("").intent == Intent.UNKNOWN

    def test_entity_overrides_greeting(self):
        """If entities are found, intent should be PROVIDE_INFO not GREETING."""
        result = p("hi, I'd like a table for 4")
        assert result.intent == Intent.PROVIDE_INFO
        assert result.party_size == 4

    def test_cancel_priority_over_confirm(self):
        """Cancel should take priority over confirm keywords."""
        assert p("cancel, no wait yes").intent == Intent.CANCEL


# ===================================================================
# Date extraction
# ===================================================================

class TestDateExtraction:

    def test_today(self):
        assert p("today").date == "2025-01-15"

    def test_tomorrow(self):
        assert p("tomorrow").date == "2025-01-16"

    def test_day_after_tomorrow(self):
        assert p("day after tomorrow").date == "2025-01-17"

    def test_day_name_friday(self):
        # 2025-01-15 is Wednesday, so Friday = +2
        assert p("friday").date == "2025-01-17"

    def test_day_name_wednesday_next_week(self):
        # "wednesday" when today is Wednesday → next Wednesday (+7)
        assert p("wednesday").date == "2025-01-22"

    def test_next_friday(self):
        # "next friday" from Wednesday = friday of NEXT week
        # This week's Friday is Jan 17, next week's Friday is Jan 24
        assert p("next friday").date == "2025-01-24"

    def test_this_saturday(self):
        # "this saturday" from Wed → Jan 18
        assert p("this saturday").date == "2025-01-18"

    def test_month_day_january_20(self):
        assert p("january 20").date == "2025-01-20"

    def test_month_day_with_ordinal(self):
        assert p("january 20th").date == "2025-01-20"

    def test_month_abbreviation(self):
        assert p("feb 14").date == "2025-02-14"

    def test_day_of_month(self):
        assert p("5th of march").date == "2025-03-05"

    def test_past_month_rolls_to_next_year(self):
        # Jan 10 is before our ref Jan 15 → should roll to 2026
        assert p("january 10").date == "2026-01-10"

    def test_mm_dd_format(self):
        assert p("2/14").date == "2025-02-14"

    def test_mm_dd_dash_format(self):
        assert p("3-25").date == "2025-03-25"

    def test_ordinal_the_20th(self):
        assert p("the 20th").date == "2025-01-20"

    def test_ordinal_past_day_rolls_to_next_month(self):
        # "the 10th" — Jan 10 is past ref Jan 15, so → Feb 10
        assert p("the 10th").date == "2025-02-10"

    def test_no_date(self):
        assert p("hello there").date is None

    def test_date_in_sentence(self):
        assert p("I want to book for tomorrow").date == "2025-01-16"


# ===================================================================
# Time extraction
# ===================================================================

class TestTimeExtraction:

    def test_7pm(self):
        assert p("7pm").time == "19:00"

    def test_7_pm_space(self):
        assert p("7 pm").time == "19:00"

    def test_730pm(self):
        assert p("7:30pm").time == "19:30"

    def test_730_pm_space(self):
        assert p("7:30 pm").time == "19:30"

    def test_12pm(self):
        assert p("12pm").time == "12:00"

    def test_12am(self):
        assert p("12am").time == "00:00"

    def test_11am(self):
        assert p("11am").time == "11:00"

    def test_24h_format(self):
        assert p("19:00").time == "19:00"

    def test_24h_format_2130(self):
        assert p("21:30").time == "21:30"

    def test_noon(self):
        assert p("noon").time == "12:00"

    def test_midday(self):
        assert p("midday").time == "12:00"

    def test_oclock(self):
        assert p("7 o'clock").time == "19:00"

    def test_half_past_seven(self):
        assert p("half past 7").time == "19:30"

    def test_no_time(self):
        assert p("tomorrow").time is None

    def test_time_in_sentence(self):
        assert p("I'd like to come at 7:30 pm").time == "19:30"

    def test_am_dot_format(self):
        assert p("11 a.m.").time == "11:00"


# ===================================================================
# Party-size extraction
# ===================================================================

class TestPartySizeExtraction:

    def test_4_people(self):
        assert p("4 people").party_size == 4

    def test_2_guests(self):
        assert p("2 guests").party_size == 2

    def test_for_4(self):
        assert p("for 4").party_size == 4

    def test_table_for_6(self):
        assert p("table for 6").party_size == 6

    def test_just_me(self):
        assert p("just me").party_size == 1

    def test_myself(self):
        assert p("myself").party_size == 1

    def test_alone(self):
        assert p("alone").party_size == 1

    def test_a_couple(self):
        assert p("a couple").party_size == 2

    def test_3_of_us(self):
        assert p("3 of us").party_size == 3

    def test_word_number_four_people(self):
        assert p("four people").party_size == 4

    def test_word_number_for_three(self):
        assert p("for three").party_size == 3

    def test_word_number_two_of_us(self):
        assert p("two of us").party_size == 2

    def test_party_of_8(self):
        assert p("party of 8").party_size == 8

    def test_no_party_size(self):
        assert p("tomorrow at 7pm").party_size is None


# ===================================================================
# Multi-entity extraction
# ===================================================================

class TestMultiEntityExtraction:

    def test_full_sentence(self):
        result = p("I'd like a table for 4 tomorrow at 7pm")
        assert result.date == "2025-01-16"
        assert result.time == "19:00"
        assert result.party_size == 4

    def test_date_and_time(self):
        result = p("friday at 7:30 pm")
        assert result.date == "2025-01-17"
        assert result.time == "19:30"

    def test_time_and_party_size(self):
        result = p("7pm for 2 people")
        assert result.time == "19:00"
        assert result.party_size == 2

    def test_date_and_party_size(self):
        result = p("tomorrow for 6 guests")
        assert result.date == "2025-01-16"
        assert result.party_size == 6


# ===================================================================
# Raw number fallback
# ===================================================================

class TestRawNumber:

    def test_bare_number(self):
        result = p("4")
        assert result.raw_number == 4
        assert result.date is None
        assert result.time is None
        assert result.party_size is None

    def test_number_word(self):
        result = p("seven")
        assert result.raw_number == 7

    def test_no_raw_when_entity_found(self):
        result = p("4 people")
        assert result.raw_number is None
        assert result.party_size == 4
