"""Rule-based date/time parsing. Pure functions; `today` is always passed in."""

import re
from datetime import date, time, timedelta
from typing import Literal

PartOfDay = Literal["morning", "afternoon"]

number_words: dict[str, int] = {
    w: i
    for i, w in enumerate(
        [
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
        ],
        start=1,
    )
}

_UNITS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth"]
_TEENS = [
    "tenth",
    "eleventh",
    "twelfth",
    "thirteenth",
    "fourteenth",
    "fifteenth",
    "sixteenth",
    "seventeenth",
    "eighteenth",
    "nineteenth",
]
ORDINAL_WORDS: dict[str, int] = {
    **{w: i for i, w in enumerate(_UNITS, start=1)},
    **{w: i for i, w in enumerate(_TEENS, start=10)},
    "twentieth": 20,
    "thirtieth": 30,
    **{f"twenty-{w}": 20 + i for i, w in enumerate(_UNITS, start=1)},
    "thirty-first": 31,
}
_ORD_RE = re.compile(r"\b(" + "|".join(sorted(ORDINAL_WORDS, key=len, reverse=True)) + r")\b")

_MONTH = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_SUF = r"(?:st|nd|rd|th)?"

_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_NUMERIC = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b")
_MONTH_FIRST = re.compile(rf"\b{_MONTH}\.?\s+(\d{{1,2}}){_SUF}\b(?:\s*,?\s*(\d{{4}})\b)?")
_DAY_FIRST = re.compile(rf"\b(\d{{1,2}}){_SUF}\s+(?:of\s+)?{_MONTH}\b(?:\s*,?\s*(\d{{4}})\b)?")
_THE_DAY = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b")
_WEEKDAY = re.compile(r"\b(?:(next|this)\s+)?(" + "|".join(_DAYS) + r")\b")


def _norm(text: str) -> str:
    """Lowercase, and turn ordinal words into digits ('fourteenth' -> '14th')."""
    return _ORD_RE.sub(lambda m: f"{ORDINAL_WORDS[m.group(1)]}th", text.lower())


def _ymd(t: str) -> tuple[int | None, int, int] | None:
    """First explicit calendar date in normalised text as (year|None, month, day)."""
    if m := _ISO.search(t):
        return int(m[1]), int(m[2]), int(m[3])
    if m := _NUMERIC.search(t):
        return (int(m[3]) if m[3] else None), int(m[1]), int(m[2])
    if m := _MONTH_FIRST.search(t):
        return (int(m[3]) if m[3] else None), _MONTHS.index(m[1][:3]) + 1, int(m[2])
    if m := _DAY_FIRST.search(t):
        return (int(m[3]) if m[3] else None), _MONTHS.index(m[2][:3]) + 1, int(m[1])
    return None


def _make(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_date(text: str, today: date) -> date | None:
    t = _norm(text)
    if "day after tomorrow" in t:
        return today + timedelta(days=2)
    if re.search(r"\btomorrow\b", t):
        return today + timedelta(days=1)
    if re.search(r"\btoday\b", t):
        return today
    if (ymd := _ymd(t)) is not None:
        y, mo, d = ymd
        if y is not None:
            return _make(y, mo, d)
        for year in (today.year, today.year + 1):
            if (c := _make(year, mo, d)) and c >= today:
                return c
        return None
    if m := _WEEKDAY.search(t):
        idx = _DAYS.index(m[2])
        if m[1] == "next":
            return today - timedelta(days=today.weekday()) + timedelta(days=7 + idx)
        return today + timedelta(days=(idx - today.weekday()) % 7)
    if m := _THE_DAY.search(t):
        day = int(m[1])
        y, mo = today.year, today.month
        for _ in range(13):  # skip months too short for this day
            if (c := _make(y, mo, day)) and c >= today:
                return c
            y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
    return None


def parse_dob(text: str, today: date | None = None) -> date | None:
    """An explicit date with a 4-digit year; rejected if after `today` (when given)."""
    ymd = _ymd(_norm(text))
    if ymd is None or ymd[0] is None:
        return None
    d = _make(*ymd)  # type: ignore[arg-type]
    if d is None or (today is not None and d > today):
        return None
    return d


_NUM = "|".join(number_words)
_AMPM = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\b")
_HHMM = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_OCLOCK = re.compile(rf"\b(\d{{1,2}}|{_NUM})\s+o'?clock\b")
_HALF = re.compile(rf"\b(half|quarter)\s+(past|to|after)\s+(\d{{1,2}}|{_NUM})\b")
_AT = re.compile(r"\bat\s+(\d{1,2})\b")


def _hour(w: str) -> int:
    return number_words.get(w) or int(w)


def _bare(h: int) -> int:
    """Clinic-hours guess for an hour without am/pm: 1-6 pm, 7-11 am, 12 noon."""
    return h + 12 if 1 <= h <= 6 else h


def parse_time(text: str) -> time | PartOfDay | None:
    t = text.lower()
    try:
        if m := _AMPM.search(t):
            h = int(m[1]) % 12 + (12 if m[3] == "p" else 0)
            return time(h, int(m[2] or 0))
        if m := _HHMM.search(t):
            h, mi = int(m[1]), int(m[2])
            return time(_bare(h), mi)
        if m := _OCLOCK.search(t):
            return time(_bare(_hour(m[1])))
        if m := _HALF.search(t):
            delta = {"half": 30, "quarter": 15}[m[1]] * (-1 if m[2] == "to" else 1)
            mins = _bare(_hour(m[3])) * 60 + delta
            return time(mins // 60, mins % 60)
        if re.search(r"\bnoon\b", t):
            return time(12)
        if m := _AT.search(t):
            return time(_bare(int(m[1])))
    except ValueError:
        return None
    if "morning" in t:
        return "morning"
    if "afternoon" in t:
        return "afternoon"
    return None
