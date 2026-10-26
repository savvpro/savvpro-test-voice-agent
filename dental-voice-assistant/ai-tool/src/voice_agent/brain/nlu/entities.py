"""Deterministic slot and entity extractors for dental voice assistant.

Extracts services, dates, times, phone numbers, names, and alternative choices
using dateparser, word2number, rapidfuzz, and regular expressions.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

import dateparser  # type: ignore[import-untyped]
from rapidfuzz import fuzz

if TYPE_CHECKING:
    from voice_agent.ports import SlotInfo

# Canonical services
SERVICES = [
    "cleaning",
    "checkup",
    "filling",
    "whitening",
    "root canal",
    "braces consultation",
]

_SERVICE_ALIASES = {
    "cleaning": ["clean", "teeth cleaning", "scale", "polishing", "hygiene"],
    "checkup": ["check up", "check-up", "examination", "exam", "routine", "consult"],
    "filling": ["cavity", "fillings", "tooth decay", "tooth hole"],
    "whitening": ["teeth whitening", "bleach", "bleaching"],
    "root canal": ["root canal treatment", "endodontic", "nerve"],
    "braces consultation": ["braces", "orthodontic", "aligners", "teeth straightening"],
}

_WORD_TO_DIGIT = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "oh": "0",
}


def extract_service(text: str) -> str | None:
    """Extract a dental service from caller text using fuzzy alias matching."""
    cleaned = text.lower().strip()
    if not cleaned:
        return None

    # Exact matches
    for s in SERVICES:
        if s in cleaned:
            return s

    # Alias matches
    for canonical, aliases in _SERVICE_ALIASES.items():
        for alias in aliases:
            if alias in cleaned:
                return canonical

    # Fuzzy matches
    words = cleaned.split()
    for s in SERVICES:
        for w in words:
            if fuzz.ratio(s, w) >= 85:
                return s

    return None


def extract_date(text: str, today: date) -> date | None:
    """Extract an appointment date relative to *today* using dateparser."""
    cleaned = text.lower().strip()
    if not cleaned:
        return None

    # Handle common relative keywords
    if "today" in cleaned:
        return today
    if "day after tomorrow" in cleaned:
        return today + timedelta(days=2)
    if "tomorrow" in cleaned:
        return today + timedelta(days=1)

    # Use dateparser with relative base date
    base_dt = datetime(today.year, today.month, today.day, 12, 0, 0)
    parsed = dateparser.parse(
        cleaned,
        settings={
            "RELATIVE_BASE": base_dt,
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )

    if parsed:
        res = parsed.date()
        # Ensure we don't accidentally parse past dates if future intended
        if res < today and ("next" in cleaned or "this" in cleaned):
            res += timedelta(days=7)
        from typing import cast

        return cast(date, res)

    return None


def extract_time(text: str) -> tuple[time | None, bool]:
    """Extract a time from caller text.

    Returns:
        (parsed_time, is_ambiguous)
        is_ambiguous is True when the caller gave a bare number like "at 5".
    """
    cleaned = text.lower().strip()
    if not cleaned:
        return None, False

    # Check for ambiguous "at 5" / "5 o'clock" / "five"
    m_ambiguous = re.search(
        r"\b(?:at\s+)?(5|five)(?:\s+o'?clock)?(?!\s*(?:am|pm|in the))\b", cleaned
    )
    if m_ambiguous and not any(
        p in cleaned for p in ["am", "pm", "morning", "evening", "afternoon"]
    ):
        return None, True

    # Check for clarification replies: "morning" -> 9 or off-hours, "evening" -> 5pm
    if cleaned in ["morning", "in the morning"]:
        return None, False  # Needs specific slot or explains 5am is closed
    if cleaned in ["evening", "in the evening"]:
        return time(17, 0), False

    # Word conversions for times (e.g. "ten in the morning")
    if "in the morning" in cleaned:
        cleaned = re.sub(r"in the morning", "am", cleaned)
    if "in the evening" in cleaned or "in the afternoon" in cleaned:
        cleaned = re.sub(r"in the (evening|afternoon)", "pm", cleaned)

    # Standard patterns: e.g. 10:30am, 10:30, 2pm, 14:00, 9 am
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", cleaned)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        meridiem = m.group(3)

        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        elif not meridiem and 1 <= hour <= 5:
            # 1..5 in dental context is 1pm..5pm (clinic hours 9-17)
            hour += 12

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute), False

    return None, False


def extract_phone(text: str) -> tuple[str | None, bool]:
    """Extract phone number and validate length (7-15 digits).

    Handles both digit strings ("03001234567") and spoken words ("zero three...").
    Returns:
        (normalized_digits, is_valid)
    """
    cleaned = text.lower().strip()
    # Convert spoken word digits to numbers
    tokens = cleaned.replace("-", " ").split()
    converted_tokens = [_WORD_TO_DIGIT.get(tok, tok) for tok in tokens]
    joined = "".join(converted_tokens)

    # Extract all digits
    digits = re.sub(r"\D", "", joined)

    if not digits:
        return None, False

    if 7 <= len(digits) <= 15:
        return digits, True

    # If digits exist but length is outside 7..15
    return digits, False


def extract_name(text: str) -> str | None:
    """Extract caller's name, discarding filler words."""
    cleaned = text.strip()
    if not cleaned:
        return None

    # Patterns like "my name is X", "i am X", "this is X"
    m = re.search(
        r"\b(?:my name is|i am|i'm|this is|call me)\s+([A-Za-z\s]+)", cleaned, re.IGNORECASE
    )
    candidate = m.group(1).strip() if m else cleaned

    # Strip conversational noise
    noise = [
        "hello",
        "hi",
        "hey",
        "please",
        "thank you",
        "thanks",
        "yes",
        "sure",
        "i want to book",
        "appointment",
        "dental",
    ]
    for n in noise:
        candidate = re.sub(rf"\b{n}\b", "", candidate, flags=re.IGNORECASE).strip()

    candidate = " ".join(candidate.split())
    # A valid name should have letters and not be a service or command
    if (
        candidate
        and all(c.isalpha() or c.isspace() for c in candidate)
        and len(candidate) >= 2
        and candidate.lower() not in SERVICES
        and candidate.lower() not in ["book", "cancel", "reschedule"]
    ):
        return candidate.title()

    return None


def extract_alternative_choice(text: str, offered_slots: list[SlotInfo]) -> SlotInfo | None:
    """Determine which offered slot the caller picked."""
    cleaned = text.lower().strip()
    if not offered_slots:
        return None

    # 1. Explicit time match first
    parsed_time, _ = extract_time(cleaned)
    if parsed_time:
        for slot in offered_slots:
            if slot.start == parsed_time:
                return slot

    # 2. First option keywords
    if any(re.search(pat, cleaned) for pat in [r"\bfirst\b", r"\b1\b", r"\bearlier\b"]):
        return offered_slots[0]

    # If caller simply says "yes" or "sure" to "Would X or Y work?", default to first
    if cleaned in ["yes", "yeah", "sure", "sounds good", "either", "ok", "okay"]:
        return offered_slots[0]

    # 3. Second option keywords
    if (
        any(re.search(pat, cleaned) for pat in [r"\bsecond\b", r"\b2\b", r"\blater\b"])
        and len(offered_slots) > 1
    ):
        return offered_slots[1]

    return None
