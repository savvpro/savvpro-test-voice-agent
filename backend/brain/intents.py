"""Rule-based intent classification.

Classifies user utterances into intents using keyword matching and
pattern rules. NO AI/LLM is used — all logic is deterministic.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional


class Intent(str, Enum):
    """Recognized user intents."""

    BOOK = "book"
    PROVIDE_DATE = "provide_date"
    PROVIDE_TIME = "provide_time"
    PROVIDE_PARTY_SIZE = "provide_party_size"
    PROVIDE_NAME = "provide_name"
    PROVIDE_CONTACT = "provide_contact"
    CONFIRM = "confirm"
    DENY = "deny"
    CHANGE = "change"
    CANCEL = "cancel"
    HELP = "help"
    GREETING = "greeting"
    GOODBYE = "goodbye"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Keyword banks — each maps to an intent
# ---------------------------------------------------------------------------

_GREETING_WORDS = {
    "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    "howdy", "greetings", "hiya", "yo",
}

_GOODBYE_WORDS = {
    "bye", "goodbye", "see you", "take care", "good night", "thanks bye",
    "that's all", "thats all", "done", "end",
}

_CONFIRM_WORDS = {
    "yes", "yeah", "yep", "yup", "sure", "correct", "absolutely",
    "that's right", "thats right", "right", "confirm", "ok", "okay",
    "sounds good", "perfect", "go ahead", "please", "do it", "book it",
    "yes please",
}

_DENY_WORDS = {
    "no", "nah", "nope", "not really", "don't", "dont", "wrong",
    "incorrect", "that's wrong", "thats wrong", "negative",
}

_CANCEL_WORDS = {
    "cancel", "nevermind", "never mind", "forget it", "stop",
    "i don't want", "i dont want", "abort",
}

_CHANGE_WORDS = {
    "change", "modify", "update", "switch", "different", "actually",
    "wait", "instead", "make it", "can we change", "let me change",
    "i want to change",
}

_HELP_WORDS = {
    "help", "what can you do", "options", "how does this work",
    "what do you do", "assist",
}

_BOOK_WORDS = {
    "book", "reserve", "reservation", "table", "booking", "make a reservation",
    "i'd like to book", "i want to book", "book a table",
}

# Patterns that strongly signal a date, time, or party-size intent
_DATE_PATTERN = re.compile(
    r"""
    (?:
        \b(?:today|tomorrow|tonight|this\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))
        | \b(?:next|this)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|weekend)
        | \b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b
        | \b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b
        | \b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:\s*,?\s*\d{4})?
        | \b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december)
        | \b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_TIME_PATTERN = re.compile(
    r"""
    (?:
        \b\d{1,2}:\d{2}\s*(?:am|pm|a\.m\.|p\.m\.)?
        | \b\d{1,2}\s*(?:am|pm|a\.m\.|p\.m\.)
        | \b(?:noon|midnight)
        | \b(?:at|around|about)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.|o'clock|oclock)?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PARTY_PATTERN = re.compile(
    r"""
    (?:
        \b(?:for|party\s+of|group\s+of|table\s+for|we\s+are|we're|we(?:\s+will|'ll)?\s+be|it(?:\s+will|'ll|'s|s)?\s+be|(?:there\s+)?(?:will\s+be|are|is|'s|s)|about|around)\s+(\d{1,2})\b
        | \b(\d{1,2})\s+(?:people|persons|guests|of\s+us|pax|seats)\b
        | \bjust\s+(?:me|myself|one|1)\b
        | \b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b
        | \b(?:a\s+)?(?:couple|pair)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def classify(text: str) -> List[Intent]:
    """Return a ranked list of intents detected in *text*.

    Multiple intents can fire when the user provides several pieces
    of information at once (e.g. "Book a table for 4 tomorrow at 7 pm").
    """
    text_lower = text.lower().strip()
    intents: List[Intent] = []

    # --- Check for cancel first (highest priority) ---
    if _matches_any(text_lower, _CANCEL_WORDS):
        intents.append(Intent.CANCEL)
        return intents  # cancel overrides everything

    # --- Change intent ---
    if _matches_any(text_lower, _CHANGE_WORDS):
        intents.append(Intent.CHANGE)

    # --- Entity-bearing intents ---
    if _DATE_PATTERN.search(text_lower):
        intents.append(Intent.PROVIDE_DATE)
    if _TIME_PATTERN.search(text_lower):
        intents.append(Intent.PROVIDE_TIME)
    if _PARTY_PATTERN.search(text_lower):
        intents.append(Intent.PROVIDE_PARTY_SIZE)

    # --- Confirmation / denial ---
    if _matches_any(text_lower, _CONFIRM_WORDS):
        if not intents:  # only if no entity intents fired
            intents.append(Intent.CONFIRM)
    if _matches_any(text_lower, _DENY_WORDS):
        if Intent.CONFIRM not in intents:
            intents.append(Intent.DENY)

    # --- Booking intent ---
    if _matches_any(text_lower, _BOOK_WORDS):
        if Intent.PROVIDE_DATE not in intents:
            intents.append(Intent.BOOK)

    # --- Greeting / goodbye ---
    if _matches_any(text_lower, _GREETING_WORDS) and not intents:
        intents.append(Intent.GREETING)
    if _matches_any(text_lower, _GOODBYE_WORDS) and not intents:
        intents.append(Intent.GOODBYE)

    # --- Help ---
    if _matches_any(text_lower, _HELP_WORDS) and not intents:
        intents.append(Intent.HELP)

    # --- Name detection (heuristic: "my name is …" / "I'm …" / "it's …") ---
    name_match = re.search(
        r"(?:my name is|i'm|i am|it's|its|name's|call me)\s+(\w+)",
        text_lower,
    )
    if name_match:
        intents.append(Intent.PROVIDE_NAME)

    # --- Contact detection (phone-like pattern) ---
    if re.search(r"\b\d{3}[\s.-]?\d{3}[\s.-]?\d{4}\b", text_lower):
        intents.append(Intent.PROVIDE_CONTACT)

    # Fallback
    if not intents:
        intents.append(Intent.UNKNOWN)

    return intents


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _matches_any(text: str, keywords: set) -> bool:
    """Check if *text* contains any keyword from the set."""
    for kw in keywords:
        if kw in text:
            return True
    return False
