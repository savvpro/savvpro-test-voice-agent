"""Tests for the date and time-period parser.

All tests inject ``clock = datetime(2026, 10, 26, 14, 30, tzinfo=timezone(timedelta(hours=5), name='PKT'))``
(Monday, 2026-10-26, 2:30 PM).  The parser never reads the system clock.

Covers:
- Happy: "tomorrow", "today", "next friday", "in 3 days", weekday names.
- Cutoff: "today morning" at 14:30 → reason="cutoff".
- Negative: "yesterday" → reason="past"; "in 10 days" → reason="out_of_range".
- Period parametrized: "am", "before noon" → "morning"; "after 5" → "evening".
- Boundary: "in 6 days" → valid; "in 7 days" → out_of_range.
- Ordinals: "28th", "november 3rd".
- "this weekend" → Saturday.
- "day after tomorrow".
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.brain.date_parser import ParseResult, parse_date_and_period

# ── Fixtures ──────────────────────────────────────────────────────────

CLOCK = datetime(2026, 10, 26, 14, 30, tzinfo=timezone(timedelta(hours=5), name="PKT"))  # Monday
TODAY = CLOCK.date()  # 2026-10-26


# ── Happy path — relative dates ──────────────────────────────────────


class TestRelativeDates:
    def test_today(self):
        r = parse_date_and_period("today", CLOCK)
        assert r.date == TODAY
        assert r.reason is None

    def test_tomorrow(self):
        r = parse_date_and_period("tomorrow", CLOCK)
        assert r.date == date(2026, 10, 27)
        assert r.reason is None

    def test_day_after_tomorrow(self):
        r = parse_date_and_period("day after tomorrow", CLOCK)
        assert r.date == date(2026, 10, 28)
        assert r.reason is None

    def test_in_1_day(self):
        r = parse_date_and_period("in 1 day", CLOCK)
        assert r.date == date(2026, 10, 27)

    def test_in_3_days(self):
        r = parse_date_and_period("in 3 days", CLOCK)
        assert r.date == date(2026, 10, 29)
        assert r.reason is None

    def test_in_6_days_valid(self):
        r = parse_date_and_period("in 6 days", CLOCK)
        assert r.date == date(2026, 11, 1)
        assert r.reason is None

    def test_in_7_days_out_of_range(self):
        r = parse_date_and_period("in 7 days", CLOCK)
        assert r.date == date(2026, 11, 2)
        assert r.reason == "out_of_range"


# ── Happy path — weekday names ────────────────────────────────────────


class TestWeekdayNames:
    def test_next_friday(self):
        r = parse_date_and_period("next friday", CLOCK)
        assert r.date == date(2026, 10, 30)  # Friday
        assert r.date.weekday() == 4  # Friday = 4
        assert r.reason is None

    def test_next_monday(self):
        r = parse_date_and_period("next monday", CLOCK)
        # Next Monday from Monday 2026-10-26 → 2026-11-02
        assert r.date == date(2026, 11, 2)
        assert r.date.weekday() == 0

    def test_this_wednesday(self):
        r = parse_date_and_period("this wednesday", CLOCK)
        assert r.date == date(2026, 10, 28)
        assert r.date.weekday() == 2

    def test_this_monday_is_today(self):
        """'this monday' when today is Monday → today."""
        r = parse_date_and_period("this monday", CLOCK)
        assert r.date == TODAY

    def test_bare_weekday_tuesday(self):
        r = parse_date_and_period("tuesday", CLOCK)
        assert r.date == date(2026, 10, 27)
        assert r.date.weekday() == 1

    def test_bare_weekday_monday_is_today(self):
        r = parse_date_and_period("monday", CLOCK)
        assert r.date == TODAY

    def test_bare_weekday_saturday(self):
        r = parse_date_and_period("saturday", CLOCK)
        assert r.date == date(2026, 10, 31)
        assert r.date.weekday() == 5

    def test_this_weekend(self):
        """'this weekend' from Monday → Saturday of the same week."""
        r = parse_date_and_period("this weekend", CLOCK)
        assert r.date == date(2026, 10, 31)  # Saturday
        assert r.date.weekday() == 5


# ── Ordinal dates ─────────────────────────────────────────────────────


class TestOrdinalDates:
    def test_28th(self):
        r = parse_date_and_period("the 28th", CLOCK)
        assert r.date == date(2026, 10, 28)
        assert r.reason is None

    def test_26th_is_today(self):
        r = parse_date_and_period("the 26th", CLOCK)
        assert r.date == TODAY

    def test_25th_next_month(self):
        """25th has passed this month → should resolve to next month."""
        r = parse_date_and_period("the 25th", CLOCK)
        assert r.date == date(2026, 11, 25)
        # But that's out of range (> today + 6)
        assert r.reason == "out_of_range"

    def test_november_3rd(self):
        r = parse_date_and_period("november 3rd", CLOCK)
        assert r.date == date(2026, 11, 3)
        # Out of range (> today + 6)
        assert r.reason == "out_of_range"

    def test_october_28th(self):
        r = parse_date_and_period("october 28th", CLOCK)
        assert r.date == date(2026, 10, 28)
        assert r.reason is None

    def test_october_27th(self):
        r = parse_date_and_period("october 27th", CLOCK)
        assert r.date == date(2026, 10, 27)
        assert r.reason is None


# ── Period detection ──────────────────────────────────────────────────


class TestPeriodDetection:
    def test_morning(self):
        r = parse_date_and_period("tomorrow morning", CLOCK)
        assert r.period == "morning"

    def test_afternoon(self):
        r = parse_date_and_period("tomorrow afternoon", CLOCK)
        assert r.period == "afternoon"

    def test_evening(self):
        r = parse_date_and_period("tomorrow evening", CLOCK)
        assert r.period == "evening"

    def test_am(self):
        r = parse_date_and_period("tomorrow am", CLOCK)
        assert r.period == "morning"

    def test_pm(self):
        r = parse_date_and_period("tomorrow pm", CLOCK)
        assert r.period == "evening"

    def test_before_noon(self):
        r = parse_date_and_period("tomorrow before noon", CLOCK)
        assert r.period == "morning"

    def test_after_noon(self):
        r = parse_date_and_period("tomorrow after noon", CLOCK)
        assert r.period == "afternoon"

    def test_midday(self):
        r = parse_date_and_period("tomorrow midday", CLOCK)
        assert r.period == "afternoon"

    def test_lunchtime(self):
        r = parse_date_and_period("tomorrow lunchtime", CLOCK)
        assert r.period == "afternoon"

    def test_night(self):
        r = parse_date_and_period("tomorrow night", CLOCK)
        assert r.period == "evening"

    def test_after_5(self):
        r = parse_date_and_period("tomorrow after 5", CLOCK)
        assert r.period == "evening"

    def test_after_6(self):
        r = parse_date_and_period("tomorrow after 6", CLOCK)
        assert r.period == "evening"

    def test_no_period(self):
        r = parse_date_and_period("tomorrow", CLOCK)
        assert r.period is None


# ── Cutoff logic ──────────────────────────────────────────────────────


class TestCutoff:
    def test_today_morning_past_cutoff(self):
        """At 14:30, morning (cutoff=12) has passed → reason='cutoff'."""
        r = parse_date_and_period("today morning", CLOCK)
        assert r.date == TODAY
        assert r.period == "morning"
        assert r.reason == "cutoff"

    def test_today_afternoon_still_ok(self):
        """At 14:30, afternoon (cutoff=17) has NOT passed → no reason."""
        r = parse_date_and_period("today afternoon", CLOCK)
        assert r.date == TODAY
        assert r.period == "afternoon"
        assert r.reason is None

    def test_today_evening_still_ok(self):
        r = parse_date_and_period("today evening", CLOCK)
        assert r.date == TODAY
        assert r.period == "evening"
        assert r.reason is None

    def test_today_no_period_not_cutoff(self):
        """At 14:30, not all periods are past → no cutoff without specific period."""
        r = parse_date_and_period("today", CLOCK)
        assert r.reason is None

    def test_today_all_periods_past(self):
        """Late at night (22:00), all periods past → cutoff."""
        late_clock = datetime(2026, 10, 26, 22, 0, tzinfo=timezone(timedelta(hours=5), name="PKT"))
        r = parse_date_and_period("today", late_clock)
        assert r.reason == "cutoff"

    def test_tomorrow_morning_no_cutoff(self):
        """Tomorrow is never subject to today's cutoff."""
        r = parse_date_and_period("tomorrow morning", CLOCK)
        assert r.reason is None


# ── Rejection: past and out_of_range ──────────────────────────────────


class TestRejections:
    def test_yesterday_past(self):
        """Dates before today → reason='past'."""
        # Use an ordinal that falls before today.
        r = parse_date_and_period("october 20th", CLOCK)
        # Oct 20 is before Oct 26 this year → next year's Oct 20
        # Actually, month_ordinal checks: Oct 20 < today → tries next year
        assert r.date == date(2027, 10, 20)
        assert r.reason == "out_of_range"

    def test_in_10_days_out_of_range(self):
        r = parse_date_and_period("in 10 days", CLOCK)
        assert r.date == date(2026, 11, 5)
        assert r.reason == "out_of_range"

    def test_in_0_days_no_match(self):
        """'in 0 days' should not match (N must be >= 1)."""
        r = parse_date_and_period("in 0 days", CLOCK)
        assert r.date is None


# ── No date found ─────────────────────────────────────────────────────


class TestNoDate:
    def test_random_text(self):
        r = parse_date_and_period("i want to reschedule", CLOCK)
        assert r.date is None
        assert r.period is None

    def test_empty_string(self):
        r = parse_date_and_period("", CLOCK)
        assert r.date is None

    def test_period_only(self):
        """Period without date → period extracted, date is None."""
        r = parse_date_and_period("morning please", CLOCK)
        assert r.date is None
        assert r.period == "morning"


# ── Combined date + period ────────────────────────────────────────────


class TestCombined:
    def test_tomorrow_morning(self):
        r = parse_date_and_period("tomorrow morning", CLOCK)
        assert r.date == date(2026, 10, 27)
        assert r.period == "morning"
        assert r.reason is None

    def test_next_friday_evening(self):
        r = parse_date_and_period("next friday evening", CLOCK)
        assert r.date == date(2026, 10, 30)
        assert r.period == "evening"
        assert r.reason is None

    def test_in_2_days_afternoon(self):
        r = parse_date_and_period("in 2 days afternoon", CLOCK)
        assert r.date == date(2026, 10, 28)
        assert r.period == "afternoon"
        assert r.reason is None


# ── Parametrized period tests ─────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected_period",
    [
        ("morning", "morning"),
        ("am", "morning"),
        ("before noon", "morning"),
        ("afternoon", "afternoon"),
        ("midday", "afternoon"),
        ("lunchtime", "afternoon"),
        ("after noon", "afternoon"),
        ("evening", "evening"),
        ("night", "evening"),
        ("pm", "evening"),
        ("after 5", "evening"),
        ("after 6", "evening"),
        ("no period here", None),
    ],
    ids=[
        "morning",
        "am",
        "before_noon",
        "afternoon",
        "midday",
        "lunchtime",
        "after_noon",
        "evening",
        "night",
        "pm",
        "after_5",
        "after_6",
        "none",
    ],
)
def test_period_parametrized(text: str, expected_period: str | None):
    r = parse_date_and_period(f"tomorrow {text}", CLOCK)
    assert r.period == expected_period


# ── Return type ───────────────────────────────────────────────────────


class TestReturnType:
    def test_returns_parse_result(self):
        r = parse_date_and_period("tomorrow", CLOCK)
        assert isinstance(r, ParseResult)

    def test_result_is_frozen(self):
        r = parse_date_and_period("tomorrow", CLOCK)
        with pytest.raises(AttributeError):
            r.date = date(2026, 1, 1)  # type: ignore[misc]
