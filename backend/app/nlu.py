"""Rule-based NLU: text -> Parsed(intent, entities). Regex/keyword/difflib only."""

import datetime as dt
import difflib
import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.clinic import DOCTORS, SPECIALTY_SYNONYMS
from app.parsing import _DAYS, _MONTHS, PartOfDay, parse_date, parse_dob, parse_time


class Intent(StrEnum):
    EMERGENCY = "emergency"
    GOODBYE = "goodbye"
    REPEAT = "repeat"
    HELP = "help"
    BOOK = "book"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"
    AFFIRM = "affirm"
    DENY = "deny"
    UNKNOWN = "unknown"


class Slot(StrEnum):
    NAME = "name"
    DOB = "dob"
    DOCTOR = "doctor"
    DATE = "date"
    TIME = "time"
    REF = "ref"
    CONFIRM = "confirm"
    CHOICE = "choice"


@dataclass
class Entities:
    name: str | None = None
    dob: dt.date | None = None
    doctor_id: str | None = None
    specialty: str | None = None
    any_doctor: bool = False
    date: dt.date | None = None
    time: dt.time | None = None
    part_of_day: PartOfDay | None = None
    ref: str | None = None
    choice: int | None = None

    def as_dict(self) -> dict[str, str]:
        out = {
            "name": self.name,
            "dob": self.dob and self.dob.isoformat(),
            "doctor_id": self.doctor_id,
            "specialty": self.specialty,
            "any_doctor": "true" if self.any_doctor else None,
            "date": self.date and self.date.isoformat(),
            "time": self.time and self.time.strftime("%H:%M"),
            "part_of_day": self.part_of_day,
            "ref": self.ref,
            "choice": None if self.choice is None else str(self.choice),
        }
        return {k: v for k, v in out.items() if v}


@dataclass
class Parsed:
    intent: Intent
    entities: Entities = field(default_factory=Entities)


# Order is the priority order; first match wins.
_INTENTS: list[tuple[Intent, re.Pattern[str]]] = [
    (
        Intent.EMERGENCY,
        re.compile(
            r"chest pain|(can'?t|cannot|can not) breathe|trouble breathing|heavy bleeding|"
            r"bleeding a lot|unconscious|passed out|\bstroke\b|heart attack|overdose|suicidal|"
            r"kill myself"
        ),
    ),
    (Intent.GOODBYE, re.compile(r"\b(bye|goodbye|that'?s all|hang up|nothing else)\b")),
    (
        Intent.REPEAT,
        re.compile(
            r"\b(repeat|pardon|say (that|it) again|come again|what was that|didn'?t (catch|hear))\b|"
            r"^(sorry|what)\b.*\?|^what\??$"
        ),
    ),
    (Intent.HELP, re.compile(r"\b(help|what can you do|how does this work)\b")),
    (Intent.CANCEL, re.compile(r"\bcancel")),
    (
        Intent.RESCHEDULE,
        re.compile(r"\b(re-?schedul|re-?book|move my appointment|change my appointment)"),
    ),
    (Intent.BOOK, re.compile(r"\b(book|appointment|see a doctor|schedule)")),
    (Intent.DENY, re.compile(r"^\s*(no|nope|nah)\b|not quite|that'?s (wrong|not right)|incorrect")),
    (
        Intent.AFFIRM,
        re.compile(
            r"\b(yes|yeah|yep|yup|correct|that'?s right|(?<!not )sure|sounds good|please do|ok|okay)\b"
        ),
    ),
]

_CLN = re.compile(r"\bC\s?L\s?N[\s-]?([A-Z0-9])\s?([A-Z0-9])\s?([A-Z0-9])\s?([A-Z0-9])\b")
_DR = re.compile(r"\b(?:dr\.?|doctor)\s+([a-z'-]+)")
_ANY = re.compile(r"\bany ?(doctor|one|body)\b|\bfirst available\b|\bdoesn'?t matter\b")
_CHOICE = re.compile(r"\b(first|1st|1|one|second|2nd|2|two|third|3rd|3|three|last)\b")
_CHOICES = {
    "first": 1,
    "1st": 1,
    "1": 1,
    "one": 1,
    "second": 2,
    "2nd": 2,
    "2": 2,
    "two": 2,
    "third": 3,
    "3rd": 3,
    "3": 3,
    "three": 3,
    "last": -1,
}
_NAME_PATTERNS = [
    re.compile(r"\bmy name(?:'s| is)\s+([a-z'-]+(?:\s+[a-z'-]+){0,3})", re.IGNORECASE),
    re.compile(r"\bname'?s\s+([a-z'-]+(?:\s+[a-z'-]+){0,3})", re.IGNORECASE),
    re.compile(
        r"^\W*(?:(?:hi|hello|hey)\W+)?this is\s+([a-z'-]+(?:\s+[a-z'-]+){0,3})", re.IGNORECASE
    ),
    re.compile(r"\bi(?:'m| am)\s+([a-z'-]+(?:\s+[a-z'-]+){0,3})", re.IGNORECASE),
]
# Words that end a captured name ("I'm looking", "Sara and I", "Sara tomorrow").
_NON_NAME = (
    {
        "looking",
        "calling",
        "trying",
        "not",
        "sure",
        "fine",
        "good",
        "having",
        "a",
        "an",
        "the",
        "here",
        "sorry",
        "and",
        "with",
        "for",
        "at",
        "on",
        "to",
        "i",
        "my",
        "me",
        "in",
        "from",
        "ok",
        "okay",
        "great",
        "well",
        "just",
        "so",
        "book",
        "booking",
        "hoping",
        "interested",
        "wondering",
        "new",
        "born",
        "would",
        "need",
        "want",
        "wanting",
        "going",
        "doing",
        "feeling",
        "today",
        "tomorrow",
        "really",
        "very",
        "yes",
        "no",
        "please",
        "thanks",
        "thank",
    }
    | set(_DAYS)
    | {m for m in _MONTHS}
)


def _clean_name(raw: str) -> str | None:
    words: list[str] = []
    for w in raw.split():
        if w.lower() in _NON_NAME:
            break
        words.append(w)
    return " ".join(words[:3]).title() if words else None


def _doctor(low: str, bare: bool) -> str | None:
    last = [d.id for d in DOCTORS]
    if m := _DR.search(low):
        got = difflib.get_close_matches(m[1], last, n=1, cutoff=0.7)
        return got[0] if got else None
    if bare:
        return next((w for w in re.findall(r"[a-z]+", low) if w in last), None)
    return None


def parse(text: str, today: dt.date, expecting: Slot | None = None) -> Parsed:
    text = text.replace("’", "'").strip()
    ent = Entities()

    if m := _CLN.search(text.upper()):
        ent.ref = "CLN-" + "".join(m.groups())
        text = (text[: m.start()] + " " + text[m.end() :]).strip()
    low = text.lower()

    intent = next((i for i, rx in _INTENTS if rx.search(low)), Intent.UNKNOWN)

    # dates: anything with a past 4-digit year (or anything when asked for DOB) is a DOB
    dob = parse_dob(low)
    if dob and (expecting == Slot.DOB or dob < today):
        ent.dob = dob
    elif expecting != Slot.DOB:
        ent.date = parse_date(low, today)

    if expecting != Slot.DOB:
        tlow = re.sub(r"\bgood (morning|afternoon|evening)\b", " ", low)
        if expecting == Slot.TIME and re.fullmatch(r"\d{1,2}", tlow.strip()):
            tlow = f"at {tlow.strip()}"
        t = parse_time(tlow)
        if isinstance(t, dt.time):
            ent.time = t
        elif t:
            ent.part_of_day = t
        if expecting == Slot.CHOICE and ent.time is None and (m := _CHOICE.search(low)):
            ent.choice = _CHOICES[m[1]]

    ent.doctor_id = _doctor(low, bare=expecting != Slot.NAME)
    if _ANY.search(low):
        ent.any_doctor = True
    if not ent.doctor_id:
        ent.specialty = next(
            (SPECIALTY_SYNONYMS[w] for w in re.findall(r"[a-z-]+", low) if w in SPECIALTY_SYNONYMS),
            None,
        )

    for rx in _NAME_PATTERNS:
        if (m := rx.search(text)) and (name := _clean_name(m[1])):
            ent.name = name
            break
    if ent.name is None and expecting == Slot.NAME and intent == Intent.UNKNOWN:
        bare = re.sub(r"[.,!?]", "", text).strip()
        if re.fullmatch(r"[A-Za-z'\- ]+", bare) and len(bare.split()) <= 4 and not ent.as_dict():
            ent.name = bare.title()

    return Parsed(intent, ent)
