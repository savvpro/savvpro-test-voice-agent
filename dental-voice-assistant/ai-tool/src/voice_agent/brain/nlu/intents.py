"""Rule-based, deterministic intent recognition for dental voice assistant.

Per AGENTS.md Hard Rule 1:
NO LLM or LLM SDK anywhere in ai-tool/. Deterministic regex & rapidfuzz only.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

INTENT_BOOK = "book"
INTENT_CANCEL = "cancel"
INTENT_RESCHEDULE = "reschedule"
INTENT_CONFIRM = "confirm"
INTENT_REJECT = "reject"
INTENT_GOODBYE = "goodbye"
INTENT_OFF_TOPIC = "off_topic"
INTENT_UNKNOWN = "unknown"

_OFF_TOPIC_KEYWORDS = [
    "weather",
    "forecast",
    "rain",
    "temperature",
    "restaurant",
    "pizza",
    "burger",
    "food",
    "hotel",
    "flight",
    "flight booking",
    "tell me a joke",
    "who made you",
    "are you human",
    "are you real",
    "president",
    "capital of",
    "recipe",
]

_GOODBYE_PATTERNS = [
    r"\b(goodbye|bye|bye-bye|see you|have a good day|that'?s all|hang up)\b",
]

_CONFIRM_PATTERNS = [
    r"^(yes|yeah|yep|yup|sure|correct|that'?s right|sounds good|confirm|please do|ok|okay)\b",
]

_REJECT_PATTERNS = [
    r"^(no|nope|nah|not really|incorrect|wrong|don'?t|cancel that|stop)\b",
]

_RESCHEDULE_PATTERNS = [
    r"\b(reschedule|change my appointment|move my appointment|different time|different day|postpone|change the date)\b",
]

_CANCEL_PATTERNS = [
    r"\b(cancel|call off|drop my appointment|won'?t be able to make it|can'?t make it)\b",
]

_BOOK_PATTERNS = [
    r"\b(book|schedule|make an appointment|new appointment|see a doctor|see a dentist|come in for|need an appointment)\b",
    r"\b(cleaning|checkup|check-up|filling|whitening|root canal|braces)\b",
]


def detect_intent(text: str) -> str:
    """Classify caller intent using regex patterns and fuzzy matching."""
    cleaned = text.strip().lower()
    if not cleaned:
        return INTENT_UNKNOWN

    # 1. Check off-topic first
    for kw in _OFF_TOPIC_KEYWORDS:
        if kw in cleaned or fuzz.partial_ratio(kw, cleaned) >= 90:
            return INTENT_OFF_TOPIC

    # 2. Check goodbye
    for pat in _GOODBYE_PATTERNS:
        if re.search(pat, cleaned):
            return INTENT_GOODBYE

    # 3. Check reschedule (before cancel, since reschedule contains change/appointment)
    for pat in _RESCHEDULE_PATTERNS:
        if re.search(pat, cleaned):
            return INTENT_RESCHEDULE

    # 4. Check cancel
    for pat in _CANCEL_PATTERNS:
        if re.search(pat, cleaned):
            return INTENT_CANCEL

    # 5. Check confirm
    for pat in _CONFIRM_PATTERNS:
        if re.search(pat, cleaned):
            return INTENT_CONFIRM

    # 6. Check reject
    for pat in _REJECT_PATTERNS:
        if re.search(pat, cleaned):
            return INTENT_REJECT

    # 7. Check book
    for pat in _BOOK_PATTERNS:
        if re.search(pat, cleaned):
            return INTENT_BOOK

    return INTENT_UNKNOWN
