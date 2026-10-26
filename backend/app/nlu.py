"""Rule-based language understanding for the dental voice assistant.

No machine-learning model is used anywhere in this file. Everything is plain
regular expressions and lookup tables, so every decision can be traced back to
a rule and unit-tested.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, time, timedelta

WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tues": 1, "tue": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thurs": 3, "thur": 3, "thu": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}
MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
SERVICES = {
    "checkup": ["check up", "checkup", "check-up", "exam", "examination",
                "consultation", "toothache", "tooth ache", "pain", "hurts", "sore"],
    "cleaning": ["cleaning", "clean", "scale and polish", "polish", "hygienist", "hygiene"],
    "filling": ["filling", "cavity", "cavities"],
    "whitening": ["whitening", "whiten", "bleaching"],
    "extraction": ["extraction", "extract", "pull a tooth", "wisdom tooth", "wisdom teeth"],
}

_MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
_DAY_RE = "|".join(sorted(WEEKDAYS, key=len, reverse=True))

EMERGENCY_RE = re.compile(
    r"\b(emergency|bleeding|swollen|swelling|knocked out|severe pain|unbearable|abscess|"
    r"can't breathe|cannot breathe|can't swallow)\b"
)
GREETING_RE = re.compile(r"\b(hello|hi|hey)( there)?\b|\bgood (morning|afternoon|evening|day)\b")

# Words that can never be part of a person's name.
NOT_NAME = (
    set(WEEKDAYS) | set(MONTHS) | set(NUM_WORDS)
    | {"urgent", "for", "about", "to", "a", "an", "the", "regarding", "in", "on", "at",
       "calling", "looking", "trying", "here", "just", "sorry", "yes", "no", "yeah",
       "okay", "ok", "please", "um", "uh", "er", "hmm", "tomorrow", "today", "tonight",
       "morning", "afternoon", "evening", "appointment", "booking", "and", "but", "not",
       "it", "its", "it's", "i", "i'm", "im", "am", "is", "my", "name", "this", "that",
       "cancel", "book", "change", "move", "reschedule"}
    | {w for words in SERVICES.values() for w in words}
)


@dataclass
class Entities:
    service: str | None = None
    day: date | None = None
    time: time | None = None
    period: str | None = None
    name: str | None = None
    emergency: bool = False

    def has_booking_info(self) -> bool:
        return any([self.service, self.day, self.time, self.period])

    def describe(self) -> str:
        found = {k: v for k, v in [
            ("service", self.service), ("day", self.day), ("time", self.time),
            ("period", self.period), ("name", self.name)] if v}
        return ", ".join(f"{k}={v}" for k, v in found.items()) or "nothing useful"


def normalize(text: str) -> str:
    t = (text or "").lower().replace("\u2019", "'")
    t = re.sub(r"\b([ap])\.m\.?", r"\1m", t)           # a.m. -> am
    t = re.sub(r"[^\w\s:'/\-]", " ", t)                # drop punctuation
    return re.sub(r"\s+", " ", t).strip()


def strip_greetings(t: str) -> str:
    return re.sub(r"\s+", " ", GREETING_RE.sub(" ", t)).strip()


def is_greeting_only(t: str) -> bool:
    return bool(t) and not strip_greetings(t)


# ---------------------------------------------------------------- intents
_INTENTS = [
    ("cancel", re.compile(r"\bcancel")),
    ("reschedule", re.compile(r"\b(re-?schedul|move (my|the|it)|change (my|the) (appointment|booking)|postpone|push (it|my))")),
    ("book", re.compile(r"\b(book|appointment|schedule|make a|set up|see (a|the) dentist|come in|visit)\b")),
    ("hours", re.compile(r"\b(opening hours|what time do you (open|close)|when (are|do) you (open|close)|are you open|your hours|what are your hours)\b")),
    ("human", re.compile(r"\b(human|operator|receptionist|real person|speak to (someone|a person)|talk to (someone|a person))\b")),
    ("repeat", re.compile(r"\b(repeat|say that again|pardon|come again|what did you say|sorry what)\b")),
    ("goodbye", re.compile(r"\b(bye|goodbye|that's all|that is all|nothing else|no thanks|no thank you|see you|have a (good|nice))\b")),
]


def detect_intent(t: str) -> str | None:
    for name, rx in _INTENTS:
        if rx.search(t):
            return name
    return None


def yes_no(t: str) -> str | None:
    if re.match(r"^(no|nope|nah)\b", t):
        return "no"
    if re.search(r"\b(yes|yeah|yep|yup|sure|correct|right|ok|okay|please do|go ahead|sounds good|that works|perfect|confirm)\b", t):
        return "yes"
    if re.search(r"\b(no|nope|nah|wrong|not right|not correct|incorrect)\b", t):
        return "no"
    return None


def ordinal_choice(t: str) -> int | None:
    """Return 0/1/2/-1 for 'first/second/third/last', 0 for 'any'."""
    if re.search(r"\b(first|1st|earliest|earlier)\b", t):
        return 0
    if re.search(r"\b(second|2nd)\b", t):
        return 1
    if re.search(r"\b(third|3rd)\b", t):
        return 2
    if re.search(r"\b(last|latest)\b", t):
        return -1
    if re.search(r"\b(any|whichever|doesn't matter|does not matter|you pick|you choose|either)\b", t):
        return 0
    return None


def change_request(t: str) -> str | None:
    """'change the time' -> 'time' (used when the caller names a slot but gives no value)."""
    if re.search(r"\b(time|hour)\b", t):
        return "time"
    if re.search(r"\b(day|date)\b", t):
        return "day"
    if re.search(r"\b(service|treatment)\b", t):
        return "service"
    return None


# ---------------------------------------------------------------- entities
def parse_service(t: str) -> str | None:
    for service, words in SERVICES.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}s?\b", t):
                return service
    return None


def parse_day(t: str, today: date) -> date | None:
    if re.search(r"\bday after tomorrow\b", t):
        return today + timedelta(days=2)
    if re.search(r"\b(tomorrow|tmrw)\b", t):
        return today + timedelta(days=1)
    if re.search(r"\btoday\b", t):
        return today

    m = re.search(rf"\b({_MONTH_RE})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", t) or None
    n = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_RE})\b", t)
    if m or n:
        month, day = (MONTHS[m.group(1)], int(m.group(2))) if m else (MONTHS[n.group(2)], int(n.group(1)))
        try:
            d = date(today.year, month, day)
            if d < today:
                d = date(today.year + 1, month, day)
            return d
        except ValueError:
            return None

    m = re.search(rf"\b(?:(next|this)\s+)?({_DAY_RE})\b", t)
    if m:
        wd = WEEKDAYS[m.group(2)]
        if m.group(1) == "next":
            start_next_week = today - timedelta(days=today.weekday()) + timedelta(days=7)
            return start_next_week + timedelta(days=wd)
        delta = (wd - today.weekday()) % 7
        if delta == 0 and m.group(1) != "this":
            delta = 7
        return today + timedelta(days=delta)

    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\b", t)
    if m:
        day = int(m.group(1))
        for add in (0, 1):
            month = today.month + add
            year = today.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            try:
                d = date(year, month, day)
            except ValueError:
                continue
            if d >= today:
                return d
    return None


def _resolve_hour(h: int, m: int, ampm: str | None) -> time | None:
    if m > 59:
        return None
    if ampm == "pm" and h < 12:
        h += 12
    elif ampm == "am" and h == 12:
        h = 0
    elif ampm is None:
        if 1 <= h <= 6:      # "at 3" means 3 PM for a dental clinic
            h += 12
    if not 0 <= h <= 23:
        return None
    return time(h, m)


def parse_time(t: str) -> time | None:
    s = t
    for word, num in NUM_WORDS.items():
        s = re.sub(rf"\b{word}\b", str(num), s)
    if re.search(r"\b(noon|midday)\b", s):
        return time(12, 0)

    m = re.search(r"\bhalf past (\d{1,2})\b", s)
    if m:
        return _resolve_hour(int(m.group(1)), 30, None)
    m = re.search(r"\bquarter past (\d{1,2})\b", s)
    if m:
        return _resolve_hour(int(m.group(1)), 15, None)
    m = re.search(r"\bquarter to (\d{1,2})\b", s)
    if m:
        return _resolve_hour((int(m.group(1)) - 1) or 12, 45, None)

    m = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", s)
    if m:
        return _resolve_hour(int(m.group(1)), int(m.group(2)), m.group(3))
    m = re.search(r"\b(\d{1,2})\s*(am|pm)\b", s)
    if m:
        return _resolve_hour(int(m.group(1)), 0, m.group(2))
    m = re.search(r"\b(\d{1,2})\s*o'?clock\b", s)
    if m:
        return _resolve_hour(int(m.group(1)), 0, None)
    m = re.search(r"\bat (\d{1,2})\b(?!\s*(?:st|nd|rd|th|:))", s)
    if m:
        return _resolve_hour(int(m.group(1)), 0, None)
    return None


def parse_period(t: str) -> str | None:
    m = re.search(r"\b(morning|afternoon|evening)\b", t)
    return m.group(1) if m else None


def _clean_name(raw: str) -> str | None:
    tokens = []
    for tok in raw.split():
        if tok in NOT_NAME:
            break
        tokens.append(tok)
        if len(tokens) == 2:
            break
    return " ".join(w.capitalize() for w in tokens) or None


def parse_name(t: str, awaiting: str | None = None) -> str | None:
    m = re.search(r"\b(?:my name is|my name's|name is|name's|this is|call me)\s+([a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,2})", t)
    if m:
        return _clean_name(m.group(1))
    if awaiting in ("name", "name_again"):
        m = re.search(r"\b(?:i am|i'm|im|it is|it's)\s+([a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,2})", t)
        if m:
            return _clean_name(m.group(1))
    return None


def bare_name(t: str) -> str | None:
    """When we just asked 'what is your name?' a short reply like 'sara khan' is the name."""
    words = t.split()
    if 1 <= len(words) <= 3 and re.fullmatch(r"[a-z][a-z'\- ]*", t):
        return _clean_name(t) if all(w not in NOT_NAME for w in words) else None
    return None


def extract(t: str, today: date, awaiting: str | None = None) -> Entities:
    ent = Entities()
    if EMERGENCY_RE.search(t):
        ent.emergency = True
    body = strip_greetings(t)
    ent.name = parse_name(body, awaiting)
    ent.service = parse_service(body)
    ent.day = parse_day(body, today)
    ent.time = parse_time(body)
    ent.period = None if ent.time else parse_period(body)
    return ent
