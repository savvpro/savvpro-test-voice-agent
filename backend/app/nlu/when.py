"""Find dates and times in what the caller said.

Everything is relative to `today` (passed in, so tests are repeatable).
Returns None when nothing was said, never a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, time, timedelta

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]
_MONTH_ABBR = {m[:3]: i + 1 for i, m in enumerate(MONTHS)}


@dataclass(frozen=True)
class TimeMention:
    value: time
    explicit_meridiem: bool  # the caller said am/pm (or noon / morning / evening)


def find_date(text: str, today: date) -> date | None:
    if re.search(r"\btoday\b", text):
        return today
    if re.search(r"\b(day after tomorrow)\b", text):
        return today + timedelta(days=2)
    if re.search(r"\btomorrow\b", text):
        return today + timedelta(days=1)
    if m := re.search(r"\bin (\d+) days?\b", text):
        return today + timedelta(days=int(m.group(1)))
    if m := re.search(r"\b(next week)\b", text):
        return today + timedelta(days=7 - today.weekday())  # next Monday

    month_pat = "|".join(MONTHS + list(_MONTH_ABBR))
    # "november 4", "nov 4th", "the 4th of november"
    if m := re.search(rf"\b({month_pat})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", text):
        return _resolve_month_day(_month(m.group(1)), int(m.group(2)), today)
    if m := re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+of\s+({month_pat})\b", text):
        return _resolve_month_day(_month(m.group(2)), int(m.group(1)), today)
    # "11/04"
    if m := re.search(r"\b(\d{1,2})/(\d{1,2})\b", text):
        return _resolve_month_day(int(m.group(1)), int(m.group(2)), today)

    for i, name in enumerate(WEEKDAYS):
        if re.search(rf"\b{name}s?\b", text):
            # "Friday" is the coming Friday (a week away if said on a Friday).
            # "Next Friday" said earlier in the same week skips to next week's.
            days = (i - today.weekday()) % 7 or 7
            if re.search(rf"\bnext {name}\b", text) and i > today.weekday():
                days += 7
            return today + timedelta(days=days)
    # "the 4th" alone
    if m := re.search(r"\bthe (\d{1,2})(?:st|nd|rd|th)\b", text):
        day = int(m.group(1))
        candidate = _safe_date(today.year, today.month, day)
        if candidate and candidate >= today:
            return candidate
        nxt = today.replace(day=1) + timedelta(days=32)
        return _safe_date(nxt.year, nxt.month, day)
    return None


def find_time(text: str) -> TimeMention | None:
    if re.search(r"\bnoon\b|\bmidday\b", text):
        return TimeMention(time(12, 0), True)
    if m := re.search(r"\bhalf past (\d{1,2})\b", text):
        return _mention(int(m.group(1)), 30, text, m.end())
    if m := re.search(r"\bquarter past (\d{1,2})\b", text):
        return _mention(int(m.group(1)), 15, text, m.end())
    if m := re.search(r"\bquarter to (\d{1,2})\b", text):
        return _mention(int(m.group(1)) - 1, 45, text, m.end())
    if m := re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", text):
        return _mention(int(m.group(1)), int(m.group(2)), text, m.end(), m.group(3))
    if m := re.search(r"\b(\d{1,2})\s*(am|pm|o'?clock)\b", text):
        mer = m.group(2) if m.group(2) in ("am", "pm") else None
        return _mention(int(m.group(1)), 0, text, m.end(), mer)
    # A bare hour after a word that introduces a time, including corrections:
    # "at 3", "around 3", "make it 4", "change it to 4", "move it to 4", "try 4".
    lead = r"at|around|about|for|by|make (?:it|that)|change (?:it|that) to|move (?:it|that) to|try|until"
    if m := re.search(rf"\b(?:{lead})\s+(\d{{1,2}})\b(?!\s*(?:st|nd|rd|th|/|days?|people|minutes))", text):
        return _mention(int(m.group(1)), 0, text, m.end())
    if m := re.search(r"\b(\d{1,2})\s+instead\b", text):  # "4 instead"
        return _mention(int(m.group(1)), 0, text, m.end())
    return None


def find_part_of_day(text: str) -> str | None:
    for part in ("morning", "afternoon", "evening"):
        if re.search(rf"\b{part}\b", text):
            return part
    return None


def _mention(hour: int, minute: int, text: str, end: int, meridiem: str | None = None) -> TimeMention | None:
    if not (0 <= minute < 60) or not (0 <= hour <= 23):
        return None
    if meridiem is None:
        tail = text[end:end + 20]
        if re.match(r"\s*(in the )?(morning)", tail):
            meridiem = "am"
        elif re.match(r"\s*(in the )?(afternoon|evening)", tail):
            meridiem = "pm"
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    if hour > 23:
        return None
    return TimeMention(time(hour, minute), meridiem is not None or hour >= 13)


def _month(name: str) -> int:
    return MONTHS.index(name) + 1 if name in MONTHS else _MONTH_ABBR[name[:3]]


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _resolve_month_day(month: int, day: int, today: date) -> date | None:
    candidate = _safe_date(today.year, month, day)
    if candidate and candidate < today:
        candidate = _safe_date(today.year + 1, month, day)
    return candidate
