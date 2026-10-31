"""Hand-written date / time / part-of-day parsing for spoken English.

No ML and no third-party parser: every rule is visible here and unit-tested.
Conventions (documented in DESIGN.md):
  * Bare hours are resolved to clinic hours: 1-6 -> PM, 7-11 -> AM, 12 -> noon.
  * A weekday name means its next occurrence strictly after today;
    "next <weekday>" means that weekday in the following calendar week.
  * Numeric dates are day/month (Pakistan style).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

_UNITS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}  # fmt: skip
_UNIT_RE = re.compile(r"\b(" + "|".join(_UNITS) + r")\b")
_WEEKDAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_MONTH_INDEX = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_MONTH = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
    "|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec"
)
_WEEKDAY = r"mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?|saturday|sunday"
_NOT_A_DATE_NEXT = r"(?!\d|\s*(?:st\b|nd\b|rd\b|th\b|/|-|(?:" + _MONTH + r")\b))"


def _words_to_digits(text: str) -> str:
    text = re.sub(r"\bforty[\s-]five\b", "45", text)
    text = re.sub(r"\bfifteen\b", "15", text)
    text = re.sub(r"\bthirty\b", "30", text)
    return _UNIT_RE.sub(lambda m: str(_UNITS[m.group(1)]), text)


# --------------------------------------------------------------------------- time
@dataclass(frozen=True)
class ParsedTime:
    value: dt.time
    assumed: bool = False  # True when AM/PM was guessed from clinic hours


def _make_time(hour: int, minute: int, meridiem: str | None = None) -> ParsedTime | None:
    if minute > 59:
        return None
    if meridiem:
        if not 1 <= hour <= 12:
            return None
        return ParsedTime(dt.time(hour % 12 + (12 if meridiem == "p" else 0), minute))
    if hour == 0 or hour > 23:
        return None
    if 1 <= hour <= 6:
        return ParsedTime(dt.time(hour + 12, minute), True)
    if 7 <= hour <= 12:
        return ParsedTime(dt.time(hour, minute), True)
    return ParsedTime(dt.time(hour, minute))  # 13-23: already 24-hour


def parse_time(text: str, expecting: bool = False) -> ParsedTime | None:
    t = _words_to_digits(text.lower())
    if re.search(r"\b(noon|midday)\b", t):
        return ParsedTime(dt.time(12, 0))
    if m := re.search(r"\bhalf past (\d{1,2})\b", t):
        return _make_time(int(m[1]), 30)
    if m := re.search(r"\bquarter past (\d{1,2})\b", t):
        return _make_time(int(m[1]), 15)
    if m := re.search(r"\bquarter to (\d{1,2})\b", t):
        hour = int(m[1])
        return _make_time(12 if hour == 1 else hour - 1, 45)
    if m := re.search(r"\b(\d{1,2})(?:[:.\s]?(\d{2}))?\s*([ap])\.?m\b\.?", t):
        return _make_time(int(m[1]), int(m[2] or 0), m[3])
    if m := re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", t):
        return _make_time(int(m[1]), int(m[2]))
    if m := re.search(
        r"\b(\d{1,2})(?::(\d{2}))?\s*(?:o'?clock\s*)?(?:in the |at |this )?(morning|afternoon|evening|night)\b", t
    ):
        return _make_time(int(m[1]), int(m[2] or 0), "a" if m[3] == "morning" else "p")
    if m := re.search(r"\b(\d{1,2})\s*o'?clock\b", t):
        return _make_time(int(m[1]), 0)
    keyword = r"\b(?:at|around|about|by|make it|say|to|for|after)\s+(\d{1,2})\b" + _NOT_A_DATE_NEXT
    if m := re.search(keyword, t):
        return _make_time(int(m[1]), 0)
    if expecting and (m := re.search(r"\b(\d{1,2})\b" + _NOT_A_DATE_NEXT, t)):
        return _make_time(int(m[1]), 0)
    return None


def parse_daypart(text: str) -> str | None:
    t = text.lower()
    if m := re.search(r"\b(morning|afternoon|evening|night)\b", t):
        return "evening" if m[1] == "night" else m[1]
    if "after lunch" in t:
        return "afternoon"
    return None


# --------------------------------------------------------------------------- date
@dataclass(frozen=True)
class ParsedDate:
    day: dt.date | None
    vague: bool = False  # "next week", "sometime": caller gave no usable day


def _safe_date(year: int, month: int, day: int) -> dt.date | None:
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def _infer_year(month: int, day: int, today: dt.date) -> dt.date | None:
    d = _safe_date(today.year, month, day)
    if d is not None and (today - d).days > 180:  # e.g. "January 5" said in December
        d = _safe_date(today.year + 1, month, day)
    return d


def parse_date(text: str, today: dt.date, expecting: bool = False) -> ParsedDate | None:
    t = _words_to_digits(text.lower())
    if re.search(r"\bday after tomorrow\b", t):
        return ParsedDate(today + dt.timedelta(days=2))
    if re.search(r"\btomorrow\b", t):
        return ParsedDate(today + dt.timedelta(days=1))
    if re.search(r"\b(today|tonight|this (?:morning|afternoon|evening))\b", t):
        return ParsedDate(today)
    if m := re.search(r"\bin (\d+|a|an) (day|days|week|weeks)\b", t):
        n = 1 if m[1] in ("a", "an") else int(m[1])
        return ParsedDate(today + dt.timedelta(days=n * (7 if m[2].startswith("week") else 1)))
    if m := re.search(r"\b(?:(next|this|coming)\s+)?(" + _WEEKDAY + r")\b", t):
        target = _WEEKDAY_INDEX[m[2][:3]]
        if m[1] == "next":
            monday = today - dt.timedelta(days=today.weekday())
            return ParsedDate(monday + dt.timedelta(days=7 + target))
        delta = (target - today.weekday()) % 7 or 7
        return ParsedDate(today + dt.timedelta(days=delta))
    if m := re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + _MONTH + r")\b", t):
        return ParsedDate(_infer_year(_MONTH_INDEX[m[2][:3]], int(m[1]), today))
    if m := re.search(r"\b(" + _MONTH + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b", t):
        return ParsedDate(_infer_year(_MONTH_INDEX[m[1][:3]], int(m[2]), today))
    if m := re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t):
        day, month = int(m[1]), int(m[2])
        if month > 12 >= day:
            day, month = month, day
        year = int(m[3]) + (2000 if m[3] and len(m[3]) == 2 else 0) if m[3] else today.year
        return ParsedDate(_safe_date(year, month, day))
    if m := re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\b", t):
        day = int(m[1])
        d = _safe_date(today.year, today.month, day)
        if d is None or d < today:
            year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
            d = _safe_date(year, month, day)
        return ParsedDate(d)
    if expecting and (m := re.fullmatch(r"\W*(\d{1,2})\W*", t)):
        day = int(m[1])
        d = _safe_date(today.year, today.month, day)
        if d is None or d < today:
            year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
            d = _safe_date(year, month, day)
        return ParsedDate(d)
    if re.search(
        r"\b(next week|this week|sometime|some time|any ?day|whenever|next month|this month|weekend|few days)\b", t
    ):
        return ParsedDate(None, vague=True)
    return None
