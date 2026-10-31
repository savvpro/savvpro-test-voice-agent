"""Rule-based language understanding: utterance text -> intents, flags and entities."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from .datetime_parse import parse_date, parse_daypart, parse_time
from .models import Intent
from .phone import extract_phone

_RESCHEDULE = re.compile(
    r"\b(re-?schedule|postpone|move (?:my|the|our) (?:appointment|booking)"
    r"|change (?:my|the) (?:appointment|booking)|shift (?:my|the) appointment)\b"
)
_CANCEL = re.compile(r"\bcancel")
_BOOK = re.compile(r"\b(book|schedule|appointment|reserve|see (?:a|the) doctor|visit|check-?up|consult)")
_EXISTING = re.compile(r"\b(existing|my appointment|already booked|previous|booked|my booking)\b")

_HUMAN = re.compile(r"\b(human|operator|real person|receptionist|representative|someone else|agent)\b")
_REPEAT = re.compile(r"\b(repeat|say that again|pardon|come again|what did you say|sorry what)\b")
_RESTART = re.compile(r"\b(start over|start again|from the beginning|begin again|restart)\b")
_ABORT = re.compile(r"\b(never ?mind|forget it|forget about it|drop it|leave it|not interested)\b")
_GOODBYE = re.compile(r"\b(bye|goodbye|good bye|that'?s all|that is all|nothing else|hang up|no more)\b")
_HOURS = re.compile(
    r"\b(opening hours|working hours|hours|timings?|what time do you (?:open|close)"
    r"|when do you (?:open|close)|are you open)\b"
)
_LOCATION = re.compile(r"\b(where are you|address|located|location|directions)\b")

_YES = re.compile(
    r"\b(yes|yeah|yep|yup|sure|correct|ok|okay|confirm(?:ed)?|go ahead|sounds good"
    r"|that'?s right|that is right|absolutely|perfect|please do|do it|right)\b"
)
_NO = re.compile(r"\b(no|nope|nah|wrong|incorrect|negative|not right|not correct|that'?s wrong)\b")

_CHANGE_DAY = re.compile(r"\b(?:different|another|other|new|change the) (?:day|date)\b")
_CHANGE_TIME = re.compile(
    r"\b(?:different|another|other|new|change the) time\b|\b(?:something|a bit) (?:later|earlier)\b"
)

_SPECIALTY = [
    ("dental", re.compile(r"\b(dentist|dental|teeth|tooth|cavity|braces)\b|\b(?:dr\.?|doctor)\s+ahmed\b")),
    ("skin", re.compile(r"\b(skin|dermatolog\w*|rash|acne)\b|\b(?:dr\.?|doctor)\s+raza\b")),
    ("general", re.compile(r"\b(general|check-?up|physician|fever|flu|cough|family doctor)\b|\b(?:dr\.?|doctor)\s+khan\b")),
]  # fmt: skip

_ORDINALS = [
    (1, re.compile(r"\b(first|1st|earliest)\b")),
    (2, re.compile(r"\b(second|2nd)\b")),
    (3, re.compile(r"\b(third|3rd)\b")),
    (-1, re.compile(r"\b(last|latest)\b")),
]

_NAME_STRONG = re.compile(r"\b(?:my name is|my name's|name is|this is|call me|name's)\s+(.+)")
_NAME_WEAK = re.compile(r"\b(?:i am|i'm|im|it's|its|it is)\s+(.+)")
_STOP_NAME = set(
    "yes no not please thanks thank you and but for at on in to from the a an my is am are was calling "
    "looking trying want would like need book booking appointment tomorrow today tonight dr doctor "
    "dentist dental skin general ok okay sure fine good just actually also with monday tuesday wednesday "
    "thursday friday saturday sunday january february march april may june july august september october "
    "november december morning afternoon evening noon cancel reschedule hello hi hey".split()
)  # fmt: skip

_PHONE_KINDS = {"phone", "phone_lookup"}
_TIME_KINDS = {"time", "offer", "other"}


@dataclass
class Parsed:
    text: str
    primary_intent: Intent | None = None
    mentions_existing: bool = False
    human: bool = False
    repeat: bool = False
    restart: bool = False
    abort: bool = False
    goodbye: bool = False
    faq: str | None = None  # "hours" | "location"
    yes: bool = False
    no: bool = False
    specialty: str | None = None
    day: dt.date | None = None
    vague_date: bool = False
    at: dt.time | None = None
    time_assumed: bool = False
    daypart: str | None = None
    name: str | None = None
    phone: str | None = None
    phone_valid: bool = False
    choice: int | None = None
    change_day: bool = False
    change_time: bool = False
    words: set[str] = field(default_factory=set)

    @property
    def has_slot_entity(self) -> bool:
        return (
            any(v is not None for v in (self.specialty, self.day, self.at, self.name, self.phone))
            or self.vague_date
            or self.daypart is not None
        )

    def labels(self) -> list[str]:
        out = []
        if self.primary_intent:
            out.append(f"intent:{self.primary_intent.value}")
        for flag in ("human", "repeat", "restart", "abort", "goodbye", "yes", "no"):
            if getattr(self, flag):
                out.append(flag)
        if self.faq:
            out.append(f"faq:{self.faq}")
        if self.choice is not None:
            out.append(f"choice:{self.choice}")
        return out

    def entities(self) -> dict[str, str]:
        ent: dict[str, str] = {}
        if self.specialty:
            ent["specialty"] = self.specialty
        if self.day:
            ent["day"] = self.day.isoformat()
        if self.vague_date:
            ent["day"] = "(vague)"
        if self.at:
            ent["time"] = self.at.strftime("%H:%M") + (" (AM/PM assumed)" if self.time_assumed else "")
        if self.daypart:
            ent["daypart"] = self.daypart
        if self.name:
            ent["name"] = self.name
        if self.phone:
            ent["phone"] = self.phone + ("" if self.phone_valid else " (invalid)")
        return ent


def _clean_name(fragment: str) -> str | None:
    words: list[str] = []
    for word in re.findall(r"[a-z][a-z'\-]*", fragment):
        if word in _STOP_NAME:
            break
        words.append(word)
        if len(words) == 3:
            break
    return " ".join(w.title() for w in words) if words else None


def _has_entity(text: str, today: dt.date) -> bool:
    return parse_time(text) is not None or parse_date(text, today) is not None


def _focus_text(text: str, today: dt.date) -> str:
    """For corrections like "4 PM, not 4 AM" keep only the side the caller wants."""
    parts = re.split(r"\b(?:not|instead of|rather than)\b", text, maxsplit=1)
    if len(parts) == 2:
        left, right = parts
        if _has_entity(left, today):
            return left
        if _has_entity(right, today):
            tail = right.rsplit(",", 1)[-1]  # "not 4 AM, 4 PM" -> the wanted value follows the comma
            return tail if _has_entity(tail, today) else right
    return text


def _extract_name(low: str, expecting: str | None) -> str | None:
    if m := _NAME_STRONG.search(low):
        return _clean_name(m[1])
    if expecting == "name":
        if m := _NAME_WEAK.search(low):
            return _clean_name(m[1])
        return _clean_name(low)
    return None


def parse(text: str, today: dt.date, expecting: str | None = None) -> Parsed:
    low = " ".join(text.lower().split())
    p = Parsed(text=text.strip())
    p.words = set(re.findall(r"[a-z']+", low))

    # --- intents and conversation-control flags -------------------------------
    if _RESCHEDULE.search(low):
        p.primary_intent = Intent.RESCHEDULE
    elif _CANCEL.search(low):
        p.primary_intent = Intent.CANCEL
    elif _BOOK.search(low):
        p.primary_intent = Intent.BOOK
    p.mentions_existing = bool(_EXISTING.search(low))
    p.human = bool(_HUMAN.search(low))
    p.repeat = bool(_REPEAT.search(low))
    p.restart = bool(_RESTART.search(low))
    p.abort = bool(_ABORT.search(low))
    p.goodbye = bool(_GOODBYE.search(low))
    if _HOURS.search(low):
        p.faq = "hours"
    elif _LOCATION.search(low):
        p.faq = "location"
    p.no = bool(_NO.search(low))
    p.yes = bool(_YES.search(low)) and not p.no
    p.change_day = bool(_CHANGE_DAY.search(low))
    p.change_time = bool(_CHANGE_TIME.search(low))
    for value, pattern in _ORDINALS:
        if pattern.search(low):
            p.choice = value
            break

    # --- entities ---------------------------------------------------------------
    phone = extract_phone(low, expecting=expecting in _PHONE_KINDS)
    p.phone, p.phone_valid = phone.digits, phone.valid
    rest = phone.remaining
    focus = _focus_text(rest, today)

    when = parse_date(focus, today, expecting=expecting == "day")
    if when is not None:
        p.day, p.vague_date = when.day, when.vague
    at = parse_time(focus, expecting=expecting in _TIME_KINDS)
    if at is not None:
        p.at, p.time_assumed = at.value, at.assumed
    p.daypart = parse_daypart(rest)
    for key, pattern in _SPECIALTY:
        if pattern.search(rest):
            p.specialty = key
            break
    p.name = _extract_name(rest, expecting)
    return p
