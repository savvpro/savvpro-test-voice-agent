"""Date and time-period parser for the REDELIVER voice assistant.

Parses natural-language date and period expressions from normalised text.
The ``clock`` is injected — this module **never** calls ``datetime.now()``
or ``date.today()``.

Supported expressions:
- Relative: "today", "tomorrow", "day after tomorrow", "in N days"
- Weekday: "monday" … "sunday", "next monday", "this friday"
- Weekend: "this weekend" → Saturday of the current week
- Ordinal: "26th", "the 28th", "november 3rd"
- Period: "morning"/"am", "afternoon"/"midday", "evening"/"night"/"pm"
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Output of :func:`parse_date_and_period`."""

    date: date | None = None
    period: str | None = None
    reason: str | None = None  # "past", "out_of_range", "cutoff"


# ── Period detection ──────────────────────────────────────────────────

_MORNING_PATTERNS = re.compile(
    r"\b(?:morning|am|before\s+noon)\b", re.IGNORECASE
)
_AFTERNOON_PATTERNS = re.compile(
    r"\b(?:afternoon|midday|lunchtime|after\s+noon)\b", re.IGNORECASE
)
_EVENING_PATTERNS = re.compile(
    r"\b(?:evening|night|pm|after\s+[56])\b", re.IGNORECASE
)

# Period cutoff hours (used for "cutoff" rejection on today).
_PERIOD_CUTOFFS: dict[str, int] = {
    "morning": 12,     # morning ends at noon
    "afternoon": 17,   # afternoon ends at 5pm
    "evening": 21,     # evening ends at 9pm
}

# Order of periods for "all past today" check.
_PERIOD_ORDER = ["morning", "afternoon", "evening"]


def _extract_period(text: str) -> str | None:
    """Extract a time-of-day period from *text*, or None."""
    if _MORNING_PATTERNS.search(text):
        return "morning"
    if _AFTERNOON_PATTERNS.search(text):
        return "afternoon"
    if _EVENING_PATTERNS.search(text):
        return "evening"
    return None


# ── Date detection ────────────────────────────────────────────────────

_WEEKDAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_IN_N_DAYS = re.compile(r"\bin\s+(\d+)\s+days?\b", re.IGNORECASE)
_ORDINAL = re.compile(
    r"\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE
)
_MONTH_ORDINAL = re.compile(
    r"\b(" + "|".join(calendar.month_name[1:]) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b",
    re.IGNORECASE,
)
_NEXT_WEEKDAY = re.compile(
    r"\bnext\s+(" + "|".join(_WEEKDAY_NAMES.keys()) + r")\b",
    re.IGNORECASE,
)
_THIS_WEEKDAY = re.compile(
    r"\bthis\s+(" + "|".join(_WEEKDAY_NAMES.keys()) + r")\b",
    re.IGNORECASE,
)
_THIS_WEEKEND = re.compile(r"\bthis\s+weekend\b", re.IGNORECASE)
_DAY_AFTER_TOMORROW = re.compile(
    r"\bday\s+after\s+tomorrow\b", re.IGNORECASE
)


def _find_next_weekday(today: date, target_dow: int) -> date:
    """Find the next occurrence of *target_dow* (0=Mon) after *today*."""
    days_ahead = target_dow - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def _extract_date(text: str, today: date) -> date | None:
    """Extract a date from *text* relative to *today*, or None."""

    # "day after tomorrow" — must check before "tomorrow"
    if _DAY_AFTER_TOMORROW.search(text):
        return today + timedelta(days=2)

    # "tomorrow"
    if re.search(r"\btomorrow\b", text, re.IGNORECASE):
        return today + timedelta(days=1)

    # "today"
    if re.search(r"\btoday\b", text, re.IGNORECASE):
        return today

    # "this weekend" → Saturday of the current week
    if _THIS_WEEKEND.search(text):
        days_to_saturday = 5 - today.weekday()
        if days_to_saturday <= 0:
            days_to_saturday += 7
        return today + timedelta(days=days_to_saturday)

    # "in N days"
    m = _IN_N_DAYS.search(text)
    if m:
        n = int(m.group(1))
        if n >= 1:
            return today + timedelta(days=n)

    # "next <weekday>"
    m = _NEXT_WEEKDAY.search(text)
    if m:
        target_dow = _WEEKDAY_NAMES[m.group(1).lower()]
        return _find_next_weekday(today, target_dow)

    # "this <weekday>"
    m = _THIS_WEEKDAY.search(text)
    if m:
        target_dow = _WEEKDAY_NAMES[m.group(1).lower()]
        # "this <weekday>" — if it's today or in the past this week, it's today;
        # otherwise it's the upcoming one this week.
        days_ahead = target_dow - today.weekday()
        if days_ahead < 0:
            # Already passed this week; treat as next week.
            days_ahead += 7
        elif days_ahead == 0:
            return today
        return today + timedelta(days=days_ahead)

    # "november 3rd" / "october 28th"
    m = _MONTH_ORDINAL.search(text)
    if m:
        month_name = m.group(1).lower()
        day_num = int(m.group(2))
        month_num = [
            calendar.month_name[i].lower() for i in range(1, 13)
        ].index(month_name) + 1
        try:
            candidate = date(today.year, month_num, day_num)
        except ValueError:
            return None
        # If the date is in the past this year, try next year.
        if candidate < today:
            try:
                candidate = date(today.year + 1, month_num, day_num)
            except ValueError:
                return None
        return candidate

    # Bare ordinal: "the 28th", "26th"
    m = _ORDINAL.search(text)
    if m:
        day_num = int(m.group(1))
        if 1 <= day_num <= 31:
            # Try current month first, then next month.
            try:
                candidate = date(today.year, today.month, day_num)
            except ValueError:
                candidate = None
            if candidate and candidate >= today:
                return candidate
            # Try next month.
            if today.month == 12:
                next_month, next_year = 1, today.year + 1
            else:
                next_month, next_year = today.month + 1, today.year
            try:
                candidate = date(next_year, next_month, day_num)
            except ValueError:
                return None
            return candidate

    # Bare weekday name (without "next" or "this")
    for name, dow in _WEEKDAY_NAMES.items():
        if re.search(r"\b" + name + r"\b", text, re.IGNORECASE):
            if dow == today.weekday():
                return today
            return _find_next_weekday(today, dow)

    return None


# ── Validation ────────────────────────────────────────────────────────

def _validate_date(
    parsed_date: date,
    today: date,
    max_date: date,
) -> str | None:
    """Return a rejection reason or None if the date is valid."""
    if parsed_date < today:
        return "past"
    if parsed_date > max_date:
        return "out_of_range"
    return None


def _check_cutoff(
    parsed_date: date,
    period: str | None,
    today: date,
    clock_hour: int,
) -> str | None:
    """Return ``\"cutoff\"`` if the requested period has already passed today."""
    if parsed_date != today:
        return None
    if period is None:
        # No specific period requested — check if ALL periods are past.
        if clock_hour >= _PERIOD_CUTOFFS["evening"]:
            return "cutoff"
        return None
    cutoff_hour = _PERIOD_CUTOFFS.get(period, 24)
    if clock_hour >= cutoff_hour:
        return "cutoff"
    return None


# ── Public API ────────────────────────────────────────────────────────

def parse_date_and_period(text: str, clock: datetime) -> ParseResult:
    """Parse a date and period from *text* using *clock* as the reference.

    Args:
        text: Normalised text (usually ``digit_text`` from the normalizer).
        clock: Injected datetime — never reads the system clock.

    Returns:
        A ``ParseResult`` with ``date``, ``period``, and optional ``reason``.
    """
    today = clock.date()
    max_date = today + timedelta(days=6)

    period = _extract_period(text)
    parsed_date = _extract_date(text, today)

    if parsed_date is None:
        return ParseResult(date=None, period=period, reason=None)

    # Validate date range.
    range_reason = _validate_date(parsed_date, today, max_date)
    if range_reason:
        return ParseResult(date=parsed_date, period=period, reason=range_reason)

    # Check today's cutoff.
    cutoff_reason = _check_cutoff(parsed_date, period, today, clock.hour)
    if cutoff_reason:
        return ParseResult(date=parsed_date, period=period, reason=cutoff_reason)

    return ParseResult(date=parsed_date, period=period, reason=None)
