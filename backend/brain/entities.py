"""Rule-based entity extraction.

Extracts structured data (dates, times, party sizes, names, contacts)
from free-form user text using regex and keyword matching.
NO AI/LLM is used.
"""

from __future__ import annotations

import re
from datetime import date, time, timedelta
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Word-to-number mapping for spoken numbers
# ---------------------------------------------------------------------------

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "a couple": 2, "couple": 2,
    "pair": 2, "myself": 1, "me": 1, "just me": 1,
}

_DAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


def extract_all(text: str) -> Dict[str, Any]:
    """Extract all recognizable entities from *text*.

    Returns a dict with keys: date, time, party_size, name, contact.
    Values are ``None`` when not detected.
    """
    return {
        "date": extract_date(text),
        "time": extract_time(text),
        "party_size": extract_party_size(text),
        "name": extract_name(text),
        "contact": extract_contact(text),
    }


# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------

def extract_date(text: str) -> Optional[date]:
    """Extract a date from user text."""
    text_lower = text.lower().strip()
    today = date.today()

    # Relative dates
    if "today" in text_lower or "tonight" in text_lower:
        return today
    if "tomorrow" in text_lower:
        return today + timedelta(days=1)

    # "this <day>" or "next <day>"
    for day_name, weekday_num in _DAY_NAMES.items():
        pattern = rf"(?:this|next)\s+{day_name}"
        if re.search(pattern, text_lower):
            is_next = "next" in text_lower.split(day_name)[0].split()[-1:] \
                if day_name in text_lower else False
            return _next_weekday(today, weekday_num, skip_this_week=bool(
                re.search(rf"\bnext\s+{day_name}", text_lower)
            ))

        # Just the day name alone (e.g. "friday")
        if re.search(rf"\b{day_name}\b", text_lower):
            return _next_weekday(today, weekday_num)

    # "Month Day" format (e.g. "January 15" or "Jan 15, 2025")
    month_day = re.search(
        r"\b("
        + "|".join(_MONTH_NAMES.keys())
        + r")\s+(\d{1,2})(?:\s*,?\s*(\d{4}))?\b",
        text_lower,
    )
    if month_day:
        month = _MONTH_NAMES[month_day.group(1)]
        day = int(month_day.group(2))
        year = int(month_day.group(3)) if month_day.group(3) else today.year
        try:
            result = date(year, month, day)
            # If the date has passed this year, assume next year
            if result < today and not month_day.group(3):
                result = date(year + 1, month, day)
            return result
        except ValueError:
            return None

    # "Day Month" format (e.g. "15th of January")
    day_month = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?("
        + "|".join(_MONTH_NAMES.keys())
        + r")\b",
        text_lower,
    )
    if day_month:
        day = int(day_month.group(1))
        month = _MONTH_NAMES[day_month.group(2)]
        try:
            result = date(today.year, month, day)
            if result < today:
                result = date(today.year + 1, month, day)
            return result
        except ValueError:
            return None

    # Numeric date: MM/DD/YYYY or DD-MM-YYYY
    numeric = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", text_lower)
    if numeric:
        a, b = int(numeric.group(1)), int(numeric.group(2))
        year = int(numeric.group(3)) if numeric.group(3) else today.year
        if year < 100:
            year += 2000
        # Try MM/DD first, then DD/MM
        for month, day in [(a, b), (b, a)]:
            try:
                result = date(year, month, day)
                if result >= today:
                    return result
            except ValueError:
                continue

    return None


def _next_weekday(from_date: date, weekday: int, skip_this_week: bool = False) -> date:
    """Return the next occurrence of *weekday* on or after *from_date*."""
    days_ahead = weekday - from_date.weekday()
    if days_ahead < 0 or (days_ahead == 0 and skip_this_week):
        days_ahead += 7
    if skip_this_week and days_ahead <= 7 and days_ahead > 0:
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)


# ---------------------------------------------------------------------------
# Time extraction
# ---------------------------------------------------------------------------

def _build_time(hour: int, minute: int, period: Optional[str]) -> Optional[time]:
    """Normalize hour/minute with optional am/pm; assume PM for ambiguous dinner hours."""
    period_norm = period.replace(".", "").strip() if period else None

    if period_norm == "pm" and hour < 12:
        hour += 12
    elif period_norm == "am" and hour == 12:
        hour = 0
    elif not period_norm and 1 <= hour <= 11:
        # Restaurant context: bare hours are evening unless explicitly am
        hour += 12

    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return time(hour, minute)
    return None


def extract_time(text: str) -> Optional[time]:
    """Extract a time from user text."""
    text_lower = text.lower().strip()

    if "noon" in text_lower:
        return time(12, 0)
    if "midnight" in text_lower:
        return time(0, 0)

    # Explicit am/pm (e.g. "7pm", "at 7:30 pm")
    match = re.search(
        r"(?:\b(?:at|around|about)\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)",
        text_lower,
    )
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        return _build_time(hour, minute, match.group(3))

    # "at 8", "around 7:30" without am/pm
    match = re.search(
        r"\b(?:at|around|about)\s+(\d{1,2})(?::(\d{2}))?\b",
        text_lower,
    )
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        return _build_time(hour, minute, None)

    # 24h-style "19:00"
    match = re.search(r"\b(\d{1,2}):(\d{2})\b", text_lower)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute)

    return None


# ---------------------------------------------------------------------------
# Party-size extraction
# ---------------------------------------------------------------------------

def extract_party_size(text: str) -> Optional[int]:
    """Extract number of guests from user text."""
    text_lower = text.lower().strip()

    # "just me" / "myself"
    if re.search(r"\bjust\s+(?:me|myself|one|1)\b", text_lower):
        return 1

    # Range patterns like "4 to 5" or "4-5"
    range_match = re.search(r"(\d{1,2})\s*(?:to|[-–])\s*(\d{1,2})", text_lower)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        return low if low <= high else high

    # "for 4", "party of 6", "table for 2", "will be 3", "it will be 3", "we are 4"
    match = re.search(
        r"(?:for|party\s+of|group\s+of|table\s+for|we\s+are|we're|we(?:\s+will|'ll)?\s+be|it(?:\s+will|'ll|'s|s)?\s+be|(?:there\s+)?(?:will\s+be|are|is|'s|s)|about|around|approx(?:\.|imately)?|just)\s+(\d{1,2})\b",
        text_lower,
    )
    if match:
        return int(match.group(1))

    # Number followed by people/guests/of us/pax
    match = re.search(r"\b(\d{1,2})\s+(?:people|persons|guests|of\s+us|pax|seats|chairs)\b", text_lower)
    if match:
        return int(match.group(1))

    # Word numbers: "will be three", "for two", "party of five"
    for word, num in _WORD_NUMBERS.items():
        pattern = rf"(?:for|party\s+of|group\s+of|table\s+for|we\s+are|we're|we(?:\s+will|'ll)?\s+be|it(?:\s+will|'ll|'s|s)?\s+be|(?:there\s+)?(?:will\s+be|are|is|'s|s)|about|around|just)\s+{word}\b"
        if re.search(pattern, text_lower):
            return num

    # Standalone word number if context is brief (e.g. "three", "four of us")
    for word, num in _WORD_NUMBERS.items():
        if re.search(rf"\b{re.escape(word)}\b", text_lower):
            if len(text_lower.split()) <= 5:
                return num

    # Standalone or isolated digit in short phrase (e.g. "will be 3", "just 3", "3")
    # Exclude times (e.g. "3pm", "3:00")
    if not re.search(r"\b\d{1,2}\s*(?::\d{2}|am|pm|a\.m\.|p\.m\.|o'clock)\b", text_lower):
        num_match = re.search(r"\b(\d{1,2})\b", text_lower)
        if num_match and len(text_lower.split()) <= 5:
            val = int(num_match.group(1))
            if 1 <= val <= 20:
                return val

    return None


# ---------------------------------------------------------------------------
# Name extraction
# ---------------------------------------------------------------------------

def extract_name(text: str) -> Optional[str]:
    """Extract a person's name from user text."""
    text_lower = text.lower().strip()

    match = re.search(
        r"(?:my name is|i'm|i am|it's|its|name's|call me)\s+(\w+(?:\s+\w+)?)",
        text_lower,
    )
    if match:
        name = match.group(1).strip()
        # Filter out common non-name words
        stop_words = {"the", "a", "an", "and", "or", "for", "at", "to", "is"}
        if name.split()[0] not in stop_words:
            return name.title()

    # If user just says a name (short text, likely answering "What's your name?")
    if len(text_lower.split()) <= 3 and text_lower.replace(" ", "").isalpha():
        # Check it's not a common word / intent keyword
        common = {
            "yes", "no", "ok", "okay", "thanks", "thank", "hi", "hello",
            "help", "cancel", "bye", "change", "book", "confirm",
        }
        words = set(text_lower.split())
        if not words & common:
            return text.strip().title()

    return None


# ---------------------------------------------------------------------------
# Contact extraction
# ---------------------------------------------------------------------------

def extract_contact(text: str) -> Optional[str]:
    """Extract a phone number from user text."""
    # Various phone formats
    match = re.search(r"(\d{3}[\s.-]?\d{3}[\s.-]?\d{4})", text)
    if match:
        return match.group(1)

    # Digits spoken with spaces (e.g. "5 5 5 1 2 3 4 5 6 7")
    digits = re.findall(r"\d", text)
    if len(digits) == 10:
        return "".join(digits)

    return None
