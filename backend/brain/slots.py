"""
Slot extractors for the restaurant booking brain.

Each extractor is a pure function: text in, optional slot value (or None) out.
No LLM, no external services. Just regex + keyword tables.

Conventions:
- Dates come back as ISO strings (YYYY-MM-DD) relative to a `now` argument.
- Times come back as 24-hour strings "HH:MM".
- Party size comes back as an int.
- Phone comes back as a cleaned string of digits (10-11 chars).
- Name comes back as a title-cased string.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Number words used for party size and spoken times
# ---------------------------------------------------------------------------
_WORD_TO_DIGIT = {
    "zero": 0, "oh": 0,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "twenty": 20,
    "couple": 2, "pair": 2, "dozen": 12,
}

_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "weds": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def _word_or_digit(token: str) -> Optional[int]:
    """Convert a token like 'seven' or '7' to an int. Returns None if neither."""
    if token in _WORD_TO_DIGIT:
        return _WORD_TO_DIGIT[token]
    try:
        n = int(token)
        if 0 <= n <= 23:
            return n
    except ValueError:
        pass
    return None


# ---------------------------------------------------------------------------
# DATE
# ---------------------------------------------------------------------------
def extract_date(text: str, now: Optional[datetime] = None) -> Optional[str]:
    """Return ISO date string YYYY-MM-DD or None."""
    if not text:
        return None
    now = now or datetime.now()
    t = text.lower().strip()

    # "today" / "tomorrow" / "day after tomorrow"
    if re.search(r"\b(today|tonight)\b", t):
        return now.date().isoformat()
    if re.search(r"\bday after tomorrow\b", t):
        return (now.date() + timedelta(days=2)).isoformat()
    if re.search(r"\btomorrow\b", t):
        return (now.date() + timedelta(days=1)).isoformat()
    m = re.search(r"\bin (\d+) days?\b", t)
    if m:
        return (now.date() + timedelta(days=int(m.group(1)))).isoformat()

    # "next friday", "this friday", "friday"
    m = re.search(r"\b(?:next|this|coming)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun)\b", t)
    if m:
        day_word = m.group(1)
        target_wd = _WEEKDAYS[day_word]
        delta = (target_wd - now.weekday()) % 7
        if "next" in t and delta == 0:
            delta = 7
        if delta == 0:
            delta = 7  # "friday" on a Friday -> next Friday
        return (now.date() + timedelta(days=delta)).isoformat()

    # "january 5", "jan 5th", "5 january", "5th of january"
    m = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?\b", t)
    if m:
        month = _MONTHS[m.group(1)]
        day = int(m.group(2))
        return _resolve_month_day(now, month, day)
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b", t)
    if m:
        day = int(m.group(1))
        month = _MONTHS[m.group(2)]
        return _resolve_month_day(now, month, day)

    # Numeric: "1/5", "2026-01-05"
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        # US convention: month/day
        try:
            year = int(m.group(3)) if m.group(3) else now.year
            if year < 100:
                year += 2000
            return date(year, a, b).isoformat()
        except ValueError:
            return None
    return None


def _resolve_month_day(now: datetime, month: int, day: int) -> Optional[str]:
    try:
        d = date(now.year, month, day)
    except ValueError:
        return None
    if d < now.date():
        # roll to next year if date already passed
        try:
            d = date(now.year + 1, month, day)
        except ValueError:
            return None
    return d.isoformat()


# ---------------------------------------------------------------------------
# TIME
# ---------------------------------------------------------------------------
def extract_time(text: str) -> Optional[str]:
    """Return 24-hour time string HH:MM or None."""
    if not text:
        return None
    t = text.lower().strip()

    # "noon" / "midnight"
    if re.search(r"\bnoon\b", t):
        return "12:00"
    if re.search(r"\bmidnight\b", t):
        return "00:00"

    # "7:30 pm", "7pm", "19:30", "7.30 pm"
    m = re.search(r"\b(\d{1,2})[:.](\d{2})\s*(a\.?m\.?|p\.?m\.?)?\b", t)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        meridiem = m.group(3)
        return _normalize_time(hour, minute, meridiem)
    m = re.search(r"\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)\b", t)
    if m:
        hour = int(m.group(1))
        meridiem = m.group(2)
        return _normalize_time(hour, 0, meridiem)

    # "seven thirty", "half past seven", "quarter past seven", "quarter to eight"
    # Also accept digit form: "half past 7", "quarter to 8", "7 thirty".
    # For restaurant booking, default word-form hours 1-10 to PM (dinner hours).
    m = re.search(r"\bhalf past (\w+)\b", t)
    if m:
        h = _word_or_digit(m.group(1))
        if h is not None:
            return _word_time(h, 30)
    m = re.search(r"\bquarter past (\w+)\b", t)
    if m:
        h = _word_or_digit(m.group(1))
        if h is not None:
            return _word_time(h, 15)
    m = re.search(r"\bquarter to (\w+)\b", t)
    if m:
        h = _word_or_digit(m.group(1))
        if h is not None:
            return _word_time(h - 1 if h > 1 else 11, 45)
    m = re.search(r"\b(\w+) thirty\b", t)
    if m:
        h = _word_or_digit(m.group(1))
        if h is not None:
            return _word_time(h, 30)
    m = re.search(r"\b(\w+) o['\"]?clock\b", t)
    if m:
        h = _word_or_digit(m.group(1))
        if h is not None:
            return _word_time(h, 0)

    # "in the evening" / "in the afternoon" / "in the morning" near a bare number
    m = re.search(r"\b(\d{1,2})(?:\s+o['\"]?clock)?\s+(in the (?:evening|afternoon|morning)|tonight|this evening)\b", t)
    if m:
        hour = int(m.group(1))
        evening = "evening" in m.group(2) or "tonight" in m.group(2)
        afternoon = "afternoon" in m.group(2)
        meridiem = "pm" if (evening or afternoon) else "am"
        return _normalize_time(hour, 0, meridiem)

    # "at 7" / "around 7" / "about 7" — must have a time-indicating preposition
    # so we don't extract "for 2" or "party of 4" as a time.
    m = re.search(r"\b(?:at|around|about)\s+(\d{1,2})(?:\s+o['\"]?clock)?\b", t)
    if m:
        # default to pm for restaurant dinner hours (most common case)
        hour = int(m.group(1))
        meridiem = "pm" if 1 <= hour <= 10 else None
        return _normalize_time(hour, 0, meridiem)

    # Bare number AS THE ENTIRE INPUT — e.g. user just said "7" when asked for a time.
    # We do NOT match bare numbers inside larger sentences (those are usually
    # party sizes, phone digits, or other values, not times).
    if re.fullmatch(r"\s*(\d{1,2})(?:\s+o['\"]?clock)?\s*", t):
        hour = int(re.match(r"\s*(\d{1,2})", t).group(1))
        if 1 <= hour <= 10:
            return _normalize_time(hour, 0, "pm")
        return _normalize_time(hour, 0, None)
    return None


def _normalize_time(hour: int, minute: int, meridiem: Optional[str]) -> Optional[str]:
    if not (0 <= minute <= 59):
        return None
    if meridiem:
        mer = meridiem.replace(".", "")
        if mer in ("pm", "p") and hour != 12:
            hour += 12
        elif mer in ("am", "a") and hour == 12:
            hour = 0
        elif mer in ("pm", "p") and hour == 12:
            hour = 12  # 12pm = noon
    if not (0 <= hour <= 23):
        return None
    return f"{hour:02d}:{minute:02d}"


def _word_time(hour: int, minute: int) -> Optional[str]:
    """Word-form times (e.g. "half past seven") default to PM for hours 1-10
    because restaurant bookings overwhelmingly happen at dinner."""
    if 1 <= hour <= 10:
        return _normalize_time(hour, minute, "pm")
    return _normalize_time(hour, minute, None)


# ---------------------------------------------------------------------------
# PARTY SIZE
# ---------------------------------------------------------------------------
def extract_party_size(text: str) -> Optional[int]:
    """Return integer party size or None."""
    if not text:
        return None
    t = text.lower().strip()

    # "just me" / "for myself" / "by myself" / "alone"
    if re.search(r"\b(?:just me|for myself|by myself|alone|solo|table for one)\b", t):
        return 1

    # "party of 4", "table for 4", "for 4 people", "4 of us", "for 4"
    m = re.search(r"\b(?:party|table|group|reservation)\s+of\s+(\d{1,2})\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(?:party|table|group|reservation)\s+for\s+(\d{1,2})\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"\bfor\s+(\d{1,2})\s+(?:people|persons|guests|pax|of us)\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"\bfor\s+(\d{1,2})\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{1,2})\s+(?:people|persons|guests|of us|pax)\b", t)
    if m:
        return int(m.group(1))
    # Word forms: "party of four", "table for two", "for six"
    m = re.search(r"\b(?:party|table|group|reservation)\s+of\s+(\w+)\b", t)
    if m and m.group(1) in _WORD_TO_DIGIT:
        n = _WORD_TO_DIGIT[m.group(1)]
        if 1 <= n <= 20:
            return n
    m = re.search(r"\b(?:party|table|group|reservation)\s+for\s+(\w+)\b", t)
    if m and m.group(1) in _WORD_TO_DIGIT:
        n = _WORD_TO_DIGIT[m.group(1)]
        if 1 <= n <= 20:
            return n
    m = re.search(r"\bfor\s+(\w+)\b", t)
    if m and m.group(1) in _WORD_TO_DIGIT:
        n = _WORD_TO_DIGIT[m.group(1)]
        if 1 <= n <= 20:
            return n
    if re.search(r"\ba couple\b", t):
        return 2
    return None


# ---------------------------------------------------------------------------
# PHONE
# ---------------------------------------------------------------------------
def extract_phone(text: str) -> Optional[str]:
    """Return cleaned digits-only phone (10-11 chars) or None."""
    if not text:
        return None
    # match common formats with separators
    m = re.search(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
    if m:
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) == 10:
            return digits
    return None


# ---------------------------------------------------------------------------
# NAME
# ---------------------------------------------------------------------------
def extract_name(text: str) -> Optional[str]:
    """Return a title-cased name string or None.

    Matches:
    - "my name is John" / "name's John" / "this is John"
    - "it's under Smith" / "book under Smith"
    - "for John"  (only if explicitly asked for name)
    - standalone capitalized word(s)
    """
    if not text:
        return None
    t = text.strip()

    patterns = [
        r"\bmy name(?:'s| is)?\s+([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){0,2})",
        r"\b(?:this is|it's|its)\s+([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){0,2})",
        r"\b(?:under|book(?:ed)? under|reservation under|for)\s+([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){0,2})",
        r"\bI'm\s+([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){0,2})",
        r"\bI am\s+([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){0,2})",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            name = m.group(1).strip().rstrip(".")
            return _title_case_name(name)

    # Last resort: a single capitalized word not at sentence start, when caller
    # is being asked for a name (the state machine calls this only in ASK_NAME).
    m = re.match(r"^\s*(?:it's\s+|this is\s+)?([A-Z][a-z]{1,15}(?:\s+[A-Z][a-z]{1,15})?)\s*[.!?]?\s*$", t)
    if m:
        return _title_case_name(m.group(1))
    return None


def _title_case_name(name: str) -> str:
    parts = [p.capitalize() for p in name.split()]
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Multi-slot extractor — pull every slot out of a single utterance in one go.
# Lets users say "I'd like to book tomorrow at 7pm for 4 people".
# ---------------------------------------------------------------------------
def extract_all(text: str, now: Optional[datetime] = None) -> dict:
    return {
        "date": extract_date(text, now),
        "time": extract_time(text),
        "party_size": extract_party_size(text),
        "phone": extract_phone(text),
        "name": extract_name(text),
    }
