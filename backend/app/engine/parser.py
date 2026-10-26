"""Deterministic intent + slot parsing. No LLM — regex, keywords, dateutil."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta


@dataclass
class ParseResult:
    intent: str
    date: Optional[str] = None  # YYYY-MM-DD
    time: Optional[str] = None  # HH:MM
    party_size: Optional[int] = None
    guest_name: Optional[str] = None
    notes: list[str] = field(default_factory=list)


# --- intent patterns ---------------------------------------------------------

_CANCEL = re.compile(
    r"\b(cancel|never\s*mind|nevermind|stop|hang\s*up|goodbye|bye|quit|end\s*(the\s*)?(call|booking))\b",
    re.I,
)
_CONFIRM = re.compile(
    r"\b(yes|yeah|yep|yup|sure|correct|confirm|book\s*it|sounds?\s*good|ok(ay)?|please\s*do|go\s*ahead)\b",
    re.I,
)
_DENY = re.compile(
    r"\b(no|nope|nah|wrong|incorrect|not\s*right|change|wait)\b",
    re.I,
)
_GREET = re.compile(
    r"\b(hi|hello|hey|good\s*(morning|afternoon|evening)|howdy)\b",
    re.I,
)
_BOOK = re.compile(
    r"\b(book|reserv(e|ation)|table|seat|dining|dinner|lunch)\b",
    re.I,
)
_CHANGE_DATE = re.compile(
    r"\b(change|switch|different|another|new)\s+(the\s+)?(date|day|night)\b|"
    r"\b(on|for)\s+(a\s+)?different\s+(date|day)\b|"
    r"\bmake\s+it\s+(on\s+)?",
    re.I,
)
_CHANGE_TIME = re.compile(
    r"\b(change|switch|different|another|new)\s+(the\s+)?time\b|"
    r"\b(at\s+)?a\s+different\s+time\b|"
    r"\bmake\s+it\s+(at\s+)?",
    re.I,
)
_CHANGE_PARTY = re.compile(
    r"\b(change|switch|different|another|new)\s+(the\s+)?(party|group|size|people|guests?)\b|"
    r"\b(for\s+)?(a\s+)?different\s+(number|size|party)\b",
    re.I,
)
_NAME = re.compile(
    r"(?:(?:my\s+name\s+is|this\s+is|i(?:'m| am)|under|for)\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    re.I,
)
_PARTY = re.compile(
    r"\b(?:party\s*(?:of|for)|for|table\s*(?:for)?|group\s*(?:of|for)?)\s*(\d{1,2})\b|"
    r"\b(\d{1,2})\s*(?:people|persons?|guests?|folks|of\s*us)\b|"
    r"^\s*(\d{1,2})\s*$",
    re.I,
)
_TIME_EXPLICIT = re.compile(
    r"\b(\d{1,2})\s*[:.]\s*(\d{2})\s*(a\.?m\.?|p\.?m\.?)?\b|"
    r"\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)\b|"
    r"\b(\d{1,2})\s*o'?clock\s*(a\.?m\.?|p\.?m\.?)?\b|"
    r"\b(?:at|around|about|by)\s+(\d{1,2})\b|"
    r"\bmake\s+it\s+(\d{1,2})\b|"
    r"\b(\d{1,2})\s+instead\b",
    re.I,
)
_OUT_OF_SCOPE = re.compile(
    r"\b(weather|uber|taxi|delivery|menu\s*price|job|hiring|stock|crypto|"
    r"news|sports|joke|sing|poem)\b",
    re.I,
)


def _normalize_ampm(hour: int, minute: int, ampm: Optional[str]) -> Optional[str]:
    if ampm:
        ampm = ampm.lower().replace(".", "")
        if ampm.startswith("p") and hour < 12:
            hour += 12
        elif ampm.startswith("a") and hour == 12:
            hour = 0
    else:
        # Bare hour with no am/pm: bias to dinner (PM) for this restaurant.
        # "at 7" / "make it 8" → 19:00 / 20:00. Out-of-hours rejected later.
        if 1 <= hour <= 11:
            hour += 12
        elif hour == 12:
            pass  # noon
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def extract_time(text: str) -> Optional[str]:
    m = _TIME_EXPLICIT.search(text)
    if not m:
        # relative phrases
        lower = text.lower()
        if "noon" in lower:
            return "12:00"
        if "midnight" in lower:
            return "00:00"
        return None

    g = m.groups()
    # (h, m, ampm) with colon
    if g[0] is not None:
        return _normalize_ampm(int(g[0]), int(g[1]), g[2])
    # (h, ampm)
    if g[3] is not None:
        return _normalize_ampm(int(g[3]), 0, g[4])
    # (h, ampm) o'clock
    if g[5] is not None:
        return _normalize_ampm(int(g[5]), 0, g[6])
    # bare hour after at/around/make it / instead — dinner bias
    for idx in (7, 8, 9):
        if g[idx] is not None:
            return _normalize_ampm(int(g[idx]), 0, None)
    return None


def extract_date(text: str, today: Optional[date] = None) -> Optional[str]:
    today = today or date.today()
    lower = text.lower().strip()

    if re.search(r"\btoday\b", lower):
        return today.isoformat()
    if re.search(r"\btomorrow\b", lower):
        return (today + timedelta(days=1)).isoformat()
    if re.search(r"\bday\s+after\s+tomorrow\b", lower):
        return (today + timedelta(days=2)).isoformat()

    # next <weekday>
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    m = re.search(
        r"\b(next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        lower,
    )
    if m:
        want = weekdays[m.group(2)]
        force_next = bool(m.group(1))
        delta = (want - today.weekday()) % 7
        if delta == 0:
            delta = 7 if force_next else 0
        elif force_next and delta < 7:
            # "next Friday" → the Friday of next week if today is before Friday
            if today.weekday() < want:
                delta += 7
        return (today + timedelta(days=delta)).isoformat()

    # Strip time-ish bits so dateutil doesn't confuse them
    cleaned = _TIME_EXPLICIT.sub(" ", text)
    cleaned = re.sub(
        r"\b(at|for|party|people|guests?|table|book|reserve|reservation)\b",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned or cleaned.isdigit():
        return None

    try:
        # Prefer dates near "today"; don't invent distant years silently
        parsed = date_parser.parse(
            cleaned,
            fuzzy=True,
            default=datetime(today.year, today.month, today.day, 12, 0),
        )
        d = parsed.date()
        # If the parsed date is in the past (same year), nudge forward a year
        if d < today:
            d = d + relativedelta(years=1)
        # Reject absurd far-future (> 1 year out) unless user said a year
        if d > today + relativedelta(years=1) and not re.search(r"\b20\d{2}\b", text):
            return None
        return d.isoformat()
    except (ValueError, OverflowError, TypeError):
        return None


def extract_party(text: str) -> Optional[int]:
    m = _PARTY.search(text)
    if not m:
        return None
    raw = next(g for g in m.groups() if g is not None)
    n = int(raw)
    if 1 <= n <= 20:
        return n
    return None


def extract_name(text: str) -> Optional[str]:
    m = _NAME.search(text)
    if m:
        return m.group(1).strip().title()
    return None


def parse_utterance(text: str, today: Optional[date] = None) -> ParseResult:
    """Pull intent + any slots mentioned in one free-form turn."""
    text = (text or "").strip()
    notes: list[str] = []
    if not text:
        return ParseResult(intent="unclear", notes=["empty input"])

    if _CANCEL.search(text):
        return ParseResult(intent="cancel", notes=["matched cancel/goodbye"])

    if _OUT_OF_SCOPE.search(text) and not _BOOK.search(text):
        return ParseResult(intent="out_of_scope", notes=["off-topic keywords"])

    date_val = extract_date(text, today=today)
    time_val = extract_time(text)
    party_val = extract_party(text)
    name_val = extract_name(text)

    if date_val:
        notes.append(f"date={date_val}")
    if time_val:
        notes.append(f"time={time_val}")
    if party_val:
        notes.append(f"party={party_val}")
    if name_val:
        notes.append(f"name={name_val}")

    # Preference order for intent when multiple signals appear
    if date_val or time_val or party_val:
        # Caller is supplying booking info — treat as provide_info
        # unless they explicitly ask to change something
        if _CHANGE_TIME.search(text) and time_val:
            intent = "change_time"
        elif _CHANGE_DATE.search(text) and date_val:
            intent = "change_date"
        elif _CHANGE_PARTY.search(text) and party_val:
            intent = "change_party"
        else:
            intent = "provide_info"
    elif _CHANGE_TIME.search(text):
        intent = "change_time"
    elif _CHANGE_DATE.search(text):
        intent = "change_date"
    elif _CHANGE_PARTY.search(text):
        intent = "change_party"
    elif _CONFIRM.search(text):
        intent = "confirm"
    elif _DENY.search(text):
        intent = "deny"
    elif _BOOK.search(text) or _GREET.search(text):
        intent = "start_booking"
    else:
        intent = "unclear"
        notes.append("no recognizable slots or keywords")

    return ParseResult(
        intent=intent,
        date=date_val,
        time=time_val,
        party_size=party_val,
        guest_name=name_val,
        notes=notes,
    )
