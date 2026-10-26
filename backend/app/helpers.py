"""Rule-based helpers: understand what the caller said.
No AI model used. Just regex + keyword matching.
"""
import re
from datetime import date, timedelta

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def get_day(text: str):
    """Extract the day from text. Returns 'Monday', '2026-10-27', etc., or None."""
    t = text.lower()
    if "today" in t:
        return date.today().isoformat()
    if "tomorrow" in t:
        return (date.today() + timedelta(days=1)).isoformat()
    for day in WEEKDAYS:
        if day in t:
            return day.capitalize()
    return None


def get_time(text: str):
    """Extract a time from text. Returns '19:00', '20:30', etc., or None."""
    t = text.lower().replace(".", "").replace(" ", "")
    m = re.search(r"(\d{1,2})(?::(\d{2}))?(am|pm)?", t)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    ampm = m.group(3)

    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    elif not ampm and 1 <= hour <= 11:
        hour += 12  # assume evening if no am/pm (restaurant context)

    if hour > 23 or minute not in (0, 15, 30, 45):
        return None
    return f"{hour:02d}:{minute:02d}"


def get_party_size(text: str):
    """Extract party size: '4', 'four people' → 4. Or None."""
    t = text.lower()
    m = re.search(r"\b(\d{1,2})\b", t)
    if m:
        return int(m.group(1))
    for word, num in NUM_WORDS.items():
        if re.search(rf"\b{word}\b", t):
            return num
    return None


def get_name(text: str):
    """Extract a name from text: 'my name is John', 'John' → 'John'. Or None."""
    m = re.search(r"(?:name is|i'm|i am|this is|it's|put|under)\s+([A-Za-z]+)", text, re.I)
    if m:
        return m.group(1).capitalize()

    # Single word fallback (e.g. caller just says "John")
    words = text.strip().split()
    if len(words) == 1 and words[0].isalpha() and words[0][0].isupper():
        if words[0].lower() not in WEEKDAYS and words[0].lower() not in NUM_WORDS:
            return words[0].capitalize()
    return None


def get_intent(text: str) -> str:
    """Classify what the caller is trying to do."""
    t = text.lower()

    if re.search(r"\b(coffee|menu|parking|wifi|vegan|gluten)\b", t):
        return "out_of_scope"
    if re.search(r"\b(cancel|call off)\b", t):
        return "cancel"
    if re.search(r"\b(bye|goodbye|see you|thanks|thank you)\b", t):
        return "goodbye"
    if re.search(r"\b(yes|yeah|yep|sure|okay|ok|correct|confirm|book it)\b", t):
        return "yes"
    if re.search(r"\b(no|nope|nah|wrong)\b", t):
        return "no"
    if re.search(r"\b(actually|wait|change|instead|make it)\b", t):
        return "change"
    if re.search(r"\b(book|reserve|table|reservation)\b", t):
        return "book"
    return "unknown"