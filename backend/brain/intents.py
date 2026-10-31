"""
Intent classification for the Clinic Appointment Voice Agent.

Patterns are checked in strict priority order.
Correction intents (change_*) are placed BEFORE provide_info so a
"actually make it Tuesday" is never misread as a raw date slot.
"""

import re
from enum import Enum


class Intent(str, Enum):
    BOOK_APPOINTMENT = "book_appointment"
    RESCHEDULE       = "reschedule"
    CANCEL           = "cancel"
    CHANGE_DOCTOR    = "change_doctor"
    CHANGE_DATE      = "change_date"
    CHANGE_TIME      = "change_time"
    CHANGE_NAME      = "change_name"
    PROVIDE_INFO     = "provide_info"
    CONFIRM          = "confirm"
    DENY             = "deny"
    REPEAT           = "repeat"
    GOODBYE          = "goodbye"
    UNCLEAR          = "unclear"


# Correction intents — intercepted before normal FSM slot filling
CORRECTION_INTENTS = {
    Intent.CHANGE_DOCTOR,
    Intent.CHANGE_DATE,
    Intent.CHANGE_TIME,
    Intent.CHANGE_NAME,
}

# Maps a correction intent to the slot key it overwrites
CORRECTION_TO_SLOT: dict[Intent, str] = {
    Intent.CHANGE_DOCTOR: "doctor",
    Intent.CHANGE_DATE:   "date",
    Intent.CHANGE_TIME:   "time",
    Intent.CHANGE_NAME:   "name",
}

# ── Regex pattern table ────────────────────────────────────────────────────────
# Each entry: (Intent, [pattern, ...]).  First match in order wins.

_PATTERNS: list[tuple[Intent, list[str]]] = [

    (Intent.GOODBYE, [
        r"\b(bye|goodbye|good\s*bye|see\s+you|farewell|take\s+care)\b",
        r"\bthat'?s\s+(all|everything)\b",
        r"^(thanks?|thank\s+you)\s*[.!]*$",
    ]),

    (Intent.CANCEL, [
        r"\b(cancel|cancell?ation|remove|delete)\b.{0,30}\b(appointment|booking|visit|slot)\b",
        r"\bi\s+(want|need|would\s+like|'d\s+like)\s+to\s+cancel\b",
        r"\bcancel\b",
    ]),

    (Intent.RESCHEDULE, [
        r"\b(reschedule|rebook)\b",
        r"\b(move|change|shift)\b.{0,30}\b(appointment|booking|visit|slot)\b",
        r"\bi\s+(want|need|would\s+like|'d\s+like)\s+to\s+(reschedule|rebook|move)\b",
    ]),

    # ── Correction intents — must come BEFORE provide_info ──────────────────
    (Intent.CHANGE_NAME, [
        r"\b(sorry|actually|oops)\b.{0,20}\bname\b",
        r"\bmy\s+name\s+is\s+actually\b",
        r"\bi\s+said\s+the\s+wrong\s+name\b",
        r"\bit'?s\s+actually\b.{0,30}\b[A-Za-z]{2,}\b",
    ]),

    (Intent.CHANGE_DOCTOR, [
        r"\b(actually|instead|change|switch|prefer|update|make\s+it)\b.{0,40}\b(dr\.?|doctor|physician|specialist|dentist)\b",
        r"\b(dr\.?|doctor)\b.{0,40}\b(instead)\b",
        r"\b(different|another|other)\s+(doctor|dr\.?|physician|specialist)\b",
        r"\bnot\s+(dr\.?|doctor)\b",
    ]),

    (Intent.CHANGE_DATE, [
        r"\b(actually|instead|change|make\s+it|switch|update)\b.{0,50}\b(date|day|monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today|next\s+\w+|\d+(?:st|nd|rd|th)?)\b",
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today|\d+(?:st|nd|rd|th)?)\b.{0,20}\b(instead)\b",
        r"\b(different|another|other)\s+(day|date)\b",
        r"\b(move\s+it\s+to|change\s+it\s+to|make\s+it)\b.{0,40}\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|\d+)\b",
    ]),

    (Intent.CHANGE_TIME, [
        r"\b(actually|instead|change|make\s+it|switch|update)\b.{0,50}(?:time|am|pm|morning|afternoon|evening|noon|\d{1,2}(?::\d{2})?)",
        r"\b(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?|morning|afternoon|evening|noon)\b.{0,20}\b(instead)\b",
        r"\b(different|another|other|earlier|later)\s+(time|slot)\b",
        r"\b(make\s+it|change\s+to|move\s+to)\b.{0,40}\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)|morning|afternoon|evening)\b",
    ]),
    # ─────────────────────────────────────────────────────────────────────────

    (Intent.CONFIRM, [
        r"^(yes|yep|yeah|yup|correct|right|that'?s?\s+right|sounds\s+good|perfect|okay|ok|"
        r"sure|absolutely|definitely|confirmed|great|good|exactly|affirmative)\s*[.,!]*$",
        r"^yes\s+(please|that'?s?\s+(right|correct))\s*[.,!]*$",
        r"^that'?s?\s+(correct|right|perfect|great)\s*[.,!]*$",
    ]),

    (Intent.DENY, [
        r"^(no|nope|nah|wrong|incorrect|that'?s?\s+wrong|not\s+right|not\s+quite|negative)\s*[.,!]*$",
        r"^no,?\s+that'?s?\s+(wrong|incorrect|not\s+right)\s*[.,!]*$",
    ]),

    (Intent.REPEAT, [
        r"\b(repeat|say\s+that\s+again|pardon|didn'?t\s+(catch|hear|understand))\b",
        r"^(what|sorry|pardon|huh)\s*[?.!]*$",
    ]),

    (Intent.BOOK_APPOINTMENT, [
        r"\b(book|schedule|make|create|set\s+up|arrange)\b.{0,40}\b(appointment|visit|consultation|booking|slot)\b",
        r"\bi\s+(need|want|would\s+like|'d\s+like)\s+(?:to\s+)?(see\s+a\s+doctor|come\s+in|make\s+an?\s+appointment|book)\b",
        r"\ban?\s+appointment\b\s*[.,!]*$",
    ]),

    # Catch-all: any remaining text is treated as slot data
    (Intent.PROVIDE_INFO, [r"."]),
]


def classify(text: str) -> Intent:
    """
    Classify *text* into the highest-priority matching Intent.
    Returns Intent.UNCLEAR only if PROVIDE_INFO somehow fails (shouldn't happen).
    """
    t = text.strip()
    for intent, patterns in _PATTERNS:
        for pattern in patterns:
            if re.search(pattern, t, re.IGNORECASE):
                return intent
    return Intent.UNCLEAR

