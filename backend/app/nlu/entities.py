"""Entity extraction from normalized text.

Extraction order matters: booking refs and phone numbers are found and masked
first so their digits are never read as dates or times; the caller's name is
masked before doctor matching so "my name is Bilal Aslam" is not a doctor.

When a caller corrects themselves ("not Monday, Friday" / "instead of 10, 11")
the negated value is skipped.
"""

import datetime as dt
import re
from collections.abc import Sequence
from functools import lru_cache

import dateparser
from pydantic import BaseModel

from app.clock import clinic_now
from app.config import get_settings
from app.nlu.fuzzy import (
    match_department,
    match_doctor,
    match_unknown_department,
    preceded_by_negation,
)
from app.nlu.lexicon import load_lexicon

# Slot names the dialogue manager can say it is waiting for.
SLOT_NAMES = ("department", "doctor", "date", "time", "patient_name", "phone", "booking_ref")


class TimeOfDay(BaseModel):
    label: str
    start: dt.time
    end: dt.time


class Entities(BaseModel):
    date: dt.date | None = None
    time: dt.time | None = None
    time_of_day: TimeOfDay | None = None
    department: str | None = None
    unknown_department: str | None = None
    doctor: str | None = None
    patient_name: str | None = None
    phone: str | None = None
    booking_ref: str | None = None

    def found(self) -> dict:
        return self.model_dump(exclude_none=True)


# --- booking reference & phone ----------------------------------------------

# "sc 4f7k" (the normalizer turns SC-4F7K into this), "s c 4 f 7 k" (spelled out),
# or "sc4f7k" glued -- glued only with a digit in it, so "screen"/"school" never match.
_BOOKING_REF = re.compile(
    r"\bs ?c (?:([a-z0-9]{4})|((?:[a-z0-9] ){3}[a-z0-9]))\b"
    r"|\bsc(?=[a-z0-9]{0,3}\d)([a-z0-9]{4})\b"
)
_PHONE = re.compile(r"(?<![\d+])(?:\+\s?92|92|0)?\s?3\d{2}\s?\d{3}\s?\d{4}(?!\d)")


def _mask(text: str, start: int, end: int) -> str:
    return text[:start] + " " * (end - start) + text[end:]


def _extract_booking_ref(text: str) -> tuple[str | None, str]:
    m = _BOOKING_REF.search(text)
    if not m:
        return None, text
    code = next(g for g in m.groups() if g).replace(" ", "").upper()
    return f"SC-{code}", _mask(text, m.start(), m.end())


def _extract_phone(text: str) -> tuple[str | None, str]:
    m = _PHONE.search(text)
    if not m:
        return None, text
    digits = re.sub(r"\D", "", m.group())
    if digits.startswith("92"):
        digits = digits[2:]
    if not digits.startswith("0"):
        digits = "0" + digits
    if not re.fullmatch(r"03\d{9}", digits):
        return None, text
    return digits, _mask(text, m.start(), m.end())


# --- dates ----------------------------------------------------------------

_WEEKDAYS = {
    "monday": "monday", "tuesday": "tuesday", "tues": "tuesday", "wednesday": "wednesday",
    "wed": "wednesday", "thursday": "thursday", "thurs": "thursday", "thur": "thursday",
    "friday": "friday", "fri": "friday", "saturday": "saturday", "sunday": "sunday",
}  # fmt: skip
# "sat", "sun" and "mon" are left out on purpose: "I sat", "the sun".
_MONTH = (
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)"
)
_ORD = r"(?:st|nd|rd|th)"
_DATE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("day_after_tomorrow", re.compile(r"\b(?:day after tomorrow|parson)\b")),
    ("tomorrow", re.compile(r"\b(?:tomorrow|tomorow|tommorow|tmrw)\b")),
    ("today", re.compile(r"\b(?:today|aaj)\b")),
    ("in_days", re.compile(r"\bin (\d{1,2}|a) (day|days|week|weeks)\b")),
    (
        "weekday",
        re.compile(r"\b(?:(this|next|coming)\s+)?(" + "|".join(_WEEKDAYS) + r")\b"),
    ),
    ("day_month", re.compile(rf"\b(?:the )?(\d{{1,2}}){_ORD}?(?: of)? ({_MONTH})\b")),
    ("month_day", re.compile(rf"\b({_MONTH}) (?:the )?(\d{{1,2}}){_ORD}?\b")),
    ("numeric", re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")),
    (
        "day_only",
        re.compile(rf"\b(?:the )?(\d{{1,2}}){_ORD}\b(?: of (this|next) month)?"),
    ),
]


@lru_cache
def _dateparser_settings_base() -> dict:
    return {
        "PREFER_DATES_FROM": "future",
        "TIMEZONE": get_settings().clinic_timezone,
        "RETURN_AS_TIMEZONE_AWARE": False,
        "DATE_ORDER": "DMY",
    }


def _dateparse(phrase: str, now: dt.datetime) -> dt.date | None:
    settings = {**_dateparser_settings_base(), "RELATIVE_BASE": now}
    parsed = dateparser.parse(phrase, languages=["en"], settings=settings)
    return parsed.date() if parsed else None


def _add_months(day: int, year: int, month: int, months: int) -> dt.date | None:
    """The `day` of the month `months` after (year, month); skips months too short for it."""
    for step in range(months, months + 12):
        y, m = divmod(month - 1 + step, 12)
        try:
            return dt.date(year + y, m + 1, day)
        except ValueError:
            continue
    return None


def _resolve_date(kind: str, m: re.Match, now: dt.datetime) -> dt.date | None:
    today = now.date()
    match kind:
        case "day_after_tomorrow":
            return today + dt.timedelta(days=2)
        case "tomorrow":
            return today + dt.timedelta(days=1)
        case "today":
            return today
        case "in_days":
            count = 1 if m.group(1) == "a" else int(m.group(1))
            days = count * (7 if m.group(2).startswith("week") else 1)
            return today + dt.timedelta(days=days)
        case "weekday":
            weekday = _WEEKDAYS[m.group(2)]
            if m.group(1) == "this" and today.strftime("%A").lower() == weekday:
                return today
            # dateparser can't parse "next monday"; with PREFER_DATES_FROM=future it
            # resolves a bare weekday to its next occurrence after today.
            return _dateparse(weekday, now)
        case "day_month" | "month_day":
            day, month = (m.group(1), m.group(2)) if kind == "day_month" else m.group(2, 1)
            if not 1 <= int(day) <= 31:
                return None
            parsed = _dateparse(f"{day} {month}", now)
            if parsed and parsed < today:  # "5 January" said in February -> next year
                parsed = _add_months(parsed.day, parsed.year, parsed.month, 12)
            return parsed
        case "numeric":
            day, month, year = m.group(1), m.group(2), m.group(3)
            if not (1 <= int(day) <= 31 and 1 <= int(month) <= 12):
                return None
            parsed = _dateparse(f"{day}/{month}" + (f"/{year}" if year else ""), now)
            if parsed and parsed < today and not year:
                parsed = _add_months(parsed.day, parsed.year, parsed.month, 12)
            return parsed
        case "day_only":
            day = int(m.group(1))
            if not 1 <= day <= 31:
                return None
            if m.group(2) == "next":
                return _add_months(day, today.year, today.month, 1)
            # dateparser keeps "the 5th" in the current month even when it has passed,
            # so roll forward to the next month that has that day.
            if day >= today.day:
                return _add_months(day, today.year, today.month, 0)
            return _add_months(day, today.year, today.month, 1)
    return None


def _extract_date(text: str, now: dt.datetime) -> tuple[dt.date | None, str]:
    candidates = []
    for kind, pattern in _DATE_PATTERNS:
        for m in pattern.finditer(text):
            candidates.append((m.start(), m.end(), kind, m))
    # Earliest mention wins; drop matches nested inside an earlier/longer one.
    candidates.sort(key=lambda c: (c[0], -(c[1] - c[0])))
    chosen: dt.date | None = None
    masked = text
    last_end = -1
    for start, end, kind, m in candidates:
        if start < last_end:
            continue
        last_end = end
        masked = _mask(masked, start, end)
        if chosen is None and not preceded_by_negation(text, start):
            chosen = _resolve_date(kind, m, now)
    return chosen, masked


# --- times ----------------------------------------------------------------

_TIME_PATTERNS = [
    re.compile(r"\b(\d{1,2}):(\d{2})(?:\s?(am|pm))?\b"),
    re.compile(r"\b(\d{1,2})()\s?(am|pm)\b"),
    # "10 in the morning", "4 this afternoon" (the time of day sets am/pm)
    re.compile(
        r"\b(\d{1,2})()()\s+(?=(?:in the |this |tomorrow )?"
        r"(?:morning|afternoon|evening|subah|shaam|dopahar)\b)"
    ),
    re.compile(
        r"\b(?:at|around|about|by|after|before|till|until|make it|to)\s+(\d{1,2})()()\b"
        r"(?!\s*(?:st|nd|rd|th|days?|weeks?|months?|minutes?|mins?|hours?|years?|people|persons?|patients?|doctors?|kids?|children)\b)(?![:/])"
    ),
]
_NOON = re.compile(r"\b(?:12 )?(?:noon|midday)\b")
_BARE_NUMBER_REPLY = re.compile(
    r"^(?:(?:at|around|maybe|ok|okay|say|how about|make it)\s+)*(\d{1,2})"
    r"(?:\s+(?:please|then|works|is fine|is good))*$"
)


def _to_time(hour: int, minute: int, meridiem: str | None, tod: TimeOfDay | None) -> dt.time | None:
    if minute > 59:
        return None
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    elif meridiem is None and 1 <= hour < 12:
        if tod is not None:
            if tod.start.hour >= 12:  # "4 in the afternoon"
                hour += 12
        elif hour <= 7:  # clinic is open 09:00-17:00, so "at 3" means 15:00
            hour += 12
    if not 0 <= hour <= 23:
        return None
    return dt.time(hour, minute)


def _extract_time(
    text: str, tod: TimeOfDay | None, expected_slot: str | None
) -> tuple[dt.time | None, str]:
    candidates = []
    for pattern in _TIME_PATTERNS:
        for m in pattern.finditer(text):
            candidates.append(m)
    noon = _NOON.search(text)
    candidates.sort(key=lambda m: m.start())

    for m in candidates:
        if preceded_by_negation(text, m.start()):
            continue
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        value = _to_time(hour, minute, m.group(3) or None, tod)
        if value is not None:
            return value, _mask(text, m.start(), m.end())
    if noon:
        return dt.time(12, 0), _mask(text, noon.start(), noon.end())
    if expected_slot == "time":
        m = _BARE_NUMBER_REPLY.match(text.strip())
        if m:
            return _to_time(int(m.group(1)), 0, None, tod), ""
    return None, text


@lru_cache
def _time_of_day_vocabulary() -> list[TimeOfDay]:
    entries = load_lexicon()["time_of_day"].items()
    vocab = [
        TimeOfDay(label=label, start=dt.time.fromisoformat(s), end=dt.time.fromisoformat(e))
        for label, (s, e) in entries
    ]
    return sorted(vocab, key=lambda t: len(t.label), reverse=True)


def _extract_time_of_day(text: str) -> TimeOfDay | None:
    for tod in _time_of_day_vocabulary():
        for m in re.finditer(rf"\b{re.escape(tod.label)}\b", text):
            if not preceded_by_negation(text, m.start()):
                return tod
    return None


# --- caller's name ----------------------------------------------------------

_STRONG_NAME = re.compile(r"\b(?:my name is|my name's|name is|mera naam|naam|call me)\s+")
_WEAK_NAME = re.compile(r"\b(?:this is|i am|i'm)\s+")
_NAME_END = {
    "and", "my", "number", "phone", "from", "calling", "speaking", "here", "hai", "please",
    "i", "i'm", "want", "would", "need", "for", "with", "the", "a", "an", "at", "on", "to",
    "is", "ji", "sir", "madam", "but", "so", "ok", "okay", "thanks", "thank",
}  # fmt: skip
_NOT_A_NAME = {
    "calling", "looking", "trying", "fine", "good", "ok", "okay", "sorry", "not", "going",
    "interested", "free", "available", "having", "sick", "unwell", "new", "back", "done", "here",
    "there", "urgent", "also", "just", "so", "very", "really", "sure", "yes", "no", "yeah",
    "nope", "hello", "hi", "in", "at", "busy", "late", "early", "patient", "worried", "confused",
    "ready", "the", "a", "an", "your", "my", "his", "her", "afraid", "glad", "happy", "feeling",
    "still", "that", "it", "what", "who", "booking", "appointment", "doctor", "dr", "clinic",
    "shifa", "care", "pregnant", "tired", "please", "thanks", "correct", "right", "wrong",
}  # fmt: skip


@lru_cache
def _vocabulary_words() -> frozenset[str]:
    """Department, symptom, weekday and time-of-day words can't be names."""
    lexicon = load_lexicon()
    words: set[str] = set(_WEEKDAYS) | {"saturday", "sunday", "today", "tomorrow"}
    for entry in lexicon["departments"].values():
        for phrase in entry["synonyms"] + entry["symptoms"]:
            words.update(phrase.split())
    for phrase in list(lexicon["unknown_departments"]) + list(lexicon["time_of_day"]):
        words.update(phrase.split())
    return frozenset(words - {"general", "family"})


def _name_tokens(rest: str) -> list[str]:
    tokens = []
    for tok in rest.split()[:3]:
        if tok in _NAME_END or not re.fullmatch(r"[a-z][a-z']*", tok):
            break
        tokens.append(tok)
    if not tokens or tokens[0] in _NOT_A_NAME or tokens[0].endswith("ing"):
        return []
    if any(t in _vocabulary_words() or t in _NOT_A_NAME for t in tokens):
        return []
    return tokens


def _extract_name(text: str, expected_slot: str | None) -> tuple[str | None, str]:
    for pattern, strong in ((_STRONG_NAME, True), (_WEAK_NAME, False)):
        for m in pattern.finditer(text):
            rest = text[m.end() :]
            tokens = _name_tokens(rest)
            if not tokens:
                continue
            after = rest.split()[len(tokens) :]
            # "i'm ali" / "this is sana malik speaking" -- but not "i am feeling ..."
            if not strong and expected_slot != "patient_name" and after and after[0] not in (
                "and", "here", "speaking", "calling", "from", "this", "my",
            ):  # fmt: skip
                continue
            span = re.match(r"\s*" + r"\s+".join(map(re.escape, tokens)), rest)
            name_end = m.end() + span.end()
            return " ".join(t.capitalize() for t in tokens), _mask(text, m.start(), name_end)

    if expected_slot == "patient_name":
        words = text.split()
        if 1 <= len(words) <= 3 and _name_tokens(text) == words:
            return " ".join(w.capitalize() for w in words), ""
    return None, text


# --- public API -------------------------------------------------------------


@lru_cache
def default_doctor_names() -> tuple[str, ...]:
    from app.db.seed import DEPARTMENTS

    return tuple(name for _, names in DEPARTMENTS.values() for name in names)


def extract_entities(
    text: str,
    now: dt.datetime | None = None,
    expected_slot: str | None = None,
    doctor_names: Sequence[str] | None = None,
) -> Entities:
    """Extract every entity from normalized ``text``.

    ``expected_slot`` is what the dialogue just asked for; it lets bare answers
    count ("3" when asked for a time, "sana malik" when asked for a name).
    """
    now = now or clinic_now()
    doctor_names = doctor_names if doctor_names is not None else default_doctor_names()
    entities = Entities()
    rest = text

    entities.booking_ref, rest = _extract_booking_ref(rest)
    entities.phone, rest = _extract_phone(rest)
    entities.patient_name, rest = _extract_name(rest, expected_slot)
    entities.date, rest = _extract_date(rest, now)
    entities.time_of_day = _extract_time_of_day(rest)
    entities.time, rest = _extract_time(rest, entities.time_of_day, expected_slot)

    doctor = match_doctor(rest, doctor_names)
    if doctor:
        entities.doctor = doctor.value
    department = match_department(rest)
    if department:
        entities.department = department.value
    else:
        unknown = match_unknown_department(rest)
        if unknown:
            entities.unknown_department = unknown.value
    return entities


# --- placeholders for the classifier -----------------------------------------

PLACEHOLDERS = {
    "booking_ref": "bookingref",
    "phone": "phonenumber",
    "date": "somedate",
    "time": "sometime",
    "time_of_day": "timeofday",
    "department": "somedepartment",
    "doctor": "somedoctor",
}


@lru_cache
def _department_names_pattern() -> re.Pattern[str]:
    phrases = [p for entry in load_lexicon()["departments"].values() for p in entry["synonyms"]]
    alternatives = "|".join(re.escape(p) for p in sorted(phrases, key=len, reverse=True))
    return re.compile(rf"\b(?:{alternatives})\b")


@lru_cache
def _doctor_names_pattern() -> re.Pattern[str]:
    parts = {part.lower() for name in default_doctor_names() for part in name.split()[1:]}
    alternatives = "|".join(sorted(parts, key=len, reverse=True))
    return re.compile(rf"\b(?:dr|doctor) (?:{alternatives})(?: (?:{alternatives}))?\b")


def delexicalize(text: str) -> str:
    """Replace entity values with placeholder words for the intent classifier.

    "book cardiology on monday at 3" -> "book somedepartment on somedate at sometime".
    The intent depends on the sentence shape, not on which day or department was
    named, so this lets a few training examples generalise to every value.
    """
    text = _BOOKING_REF.sub(f" {PLACEHOLDERS['booking_ref']} ", text)
    text = _PHONE.sub(f" {PLACEHOLDERS['phone']} ", text)
    for _, pattern in _DATE_PATTERNS:
        text = pattern.sub(f" {PLACEHOLDERS['date']} ", text)
    for pattern in _TIME_PATTERNS:
        # Keep the lead-in word ("at 3" -> "at sometime"); only the number is replaced.
        text = pattern.sub(
            lambda m: f"{m.string[m.start() : m.start(1)]}{PLACEHOLDERS['time']} ", text
        )
    text = _NOON.sub(f" {PLACEHOLDERS['time']} ", text)
    for tod in _time_of_day_vocabulary():
        text = re.sub(rf"\b{re.escape(tod.label)}\b", f" {PLACEHOLDERS['time_of_day']} ", text)
    text = _doctor_names_pattern().sub(f" {PLACEHOLDERS['doctor']} ", text)
    text = _department_names_pattern().sub(f" {PLACEHOLDERS['department']} ", text)
    return re.sub(r"\s+", " ", text).strip()
