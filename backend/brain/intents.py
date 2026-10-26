"""
Intent classifier for the restaurant booking brain.

Pure keyword + regex based. NO LLM. NO embeddings. NO model files.

The classifier returns a list of candidate intents ranked by confidence.
The state machine then chooses what to do based on the current state plus
the intent ranking. Some intents are "meta" — they don't advance the
dialogue, they request side info (ask_hours, repeat, help).

Order of evaluation matters: more specific patterns first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class Intent:
    name: str
    confidence: float
    raw: str = ""


# Each rule: (intent_name, list of regex patterns, base_confidence).
# Earlier matches win when scores tie. Longer / more specific patterns
# get a small confidence bump so "yes that's right" beats "yes".
_RULES: list[tuple[str, list[str], float]] = [
    # --- conversation control ---
    ("goodbye",      [r"\b(?:good)?bye\b", r"\bsee you\b", r"\bthat'?s all\b", r"\bhang up\b", r"\bI'?m done\b", r"\bend (?:the )?call\b"], 0.95),
    ("cancel",       [r"\bcancel\b", r"\bnever mind\b", r"\bnevermind\b", r"\bforget it\b", r"\babort\b", r"\bdon'?t book\b", r"\bcall it off\b"], 0.95),
    ("repeat",       [r"\b(?:can you\s+)?repeat\b", r"\bwhat\b\s*\?$", r"\bpardon\b", r"\bsay (?:that )?again\b", r"\bcome again\b", r"\bI didn'?t catch\b", r"\bwhat did you say\b"], 0.85),
    ("help",         [r"\bhelp\b", r"\bwhat can you do\b", r"\bhow does this work\b", r"\bwhat are my options\b"], 0.8),

    # --- meta questions about the restaurant ---
    ("ask_hours",    [r"\b(?:what (?:time|hours)|how late|until when|when (?:do you|are you))\b.*\b(?:open|close|hours?)", r"\b(?:your )?hours\b", r"\bopening hours\b", r"\bare you open\b"], 0.9),
    ("ask_location", [r"\bwhere (?:are you|is the restaurant|'?s the restaurant)\b", r"\b(?:your )?address\b", r"\blocation\b", r"\bhow do I get there\b", r"\bDirections\b"], 0.9),
    ("ask_menu",     [r"\b(?:do you|got|have)\b.*\b(?:vegetarian|vegan|gluten|kosher|halal|kids|seafood|steak|wine|beer)", r"\b(?:your )?menu\b", r"\bwhat(?: kind of)? food\b", r"\bcuisine\b"], 0.9),
    ("ask_parking",  [r"\bparking\b", r"\bvalet\b", r"\bwhere can I park\b"], 0.9),

    # --- confirmation / denial (also used for slot-level corrections) ---
    ("confirm",      [r"\byes\b", r"\byeah\b", r"\byep\b", r"\byup\b", r"\bcorrect\b", r"\bright\b", r"\bthat'?s right\b", r"\bthat'?s correct\b", r"\bsounds good\b", r"\bsounds great\b", r"\bperfect\b", r"\bbook it\b", r"\bgo ahead\b", r"\bconfirm\b", r"\bsure\b", r"\bok(?:ay)?\b\s*$", r"\buh[\s-]?huh\b"], 0.7),
    ("deny",         [r"\bno\b", r"\bnope\b", r"\bnah\b", r"\bnot really\b", r"\bthat'?s wrong\b", r"\bthat'?s not right\b", r"\bincorrect\b", r"\bnot correct\b", r"\bI don'?t think so\b"], 0.7),

    # --- change / correction (must come before provide_* so "actually change the time to 8pm" parses) ---
    # Base 0.7 so it ties with provide_* (also 0.6 + length bonus) and wins
    # because change_value is evaluated first in the rule list.
    ("change_value", [r"\b(?:actually|instead|wait|change|switch|update|make it|let'?s do|rather)\b"], 0.7),

    # --- provide_* intents ---
    ("provide_date",       [r"\b(?:today|tomorrow|tonight|day after tomorrow)\b",
                            r"\b(?:next|this|coming)?\s*(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
                            r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
                            r"\b(?:jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b",
                            r"\b\d{1,2}[-/]\d{1,2}(?:[-/]\d{2,4})?\b",
                            r"\b\d{4}-\d{2}-\d{2}\b",
                            r"\bin \d+ days?\b"], 0.6),
    ("provide_time",       [r"\b\d{1,2}\s*(?:a\.?m\.?|p\.?m\.?)\b",
                            r"\b\d{1,2}[:.]\d{2}\b",
                            r"\b(?:noon|midnight)\b",
                            r"\bhalf past\b", r"\bquarter (?:past|to)\b",
                            r"\b\w+ thirty\b",
                            r"\b(?:at|around|about)\s+\d{1,2}\b",
                            r"\bo['\"]?clock\b"], 0.6),
    ("provide_party_size", [r"\b(?:party|table|group|reservation)\s+of\s+\w+\b",
                            r"\bfor\s+\w+\s+(?:people|persons|guests|of us|pax)\b",
                            r"\bfor\s+\d{1,2}\b",
                            r"\b\d{1,2}\s+(?:people|persons|guests|of us|pax)\b",
                            r"\bjust me\b", r"\bfor myself\b", r"\bby myself\b", r"\balone\b",
                            r"\ba couple\b"], 0.6),
    ("provide_name",       [r"\bmy name\b", r"\b(?:this is|it'?s)\s+[A-Z]", r"\bunder\s+[A-Z]",
                            r"\b(?:book(?:ed)? under|reservation under)\s+[A-Z]",
                            r"\bI'?m\s+[A-Z]", r"\bI am\s+[A-Z]"], 0.55),
    ("provide_phone",      [r"\b(?:my )?(?:phone|number|cell|mobile|contact)(?:\s+(?:is|number))?\b",
                            r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
                            r"\(\d{3}\)\s*\d{3}[-.\s]?\d{4}"], 0.7),

    # --- greeting (low priority — must not beat other intents) ---
    ("greeting",    [r"\b(?:hi|hello|hey|yo|howdy|good (?:morning|afternoon|evening))\b"], 0.5),

    # --- start booking ---
    ("start_booking", [r"\b(?:I'?d like to|I want to|can I|could I|let'?s|book|reserve|reservation|table)\b"], 0.55),
]


# Quick lookup for the most common single-word intents.
_FAST_OVERRIDES = {
    "yes": "confirm", "yeah": "confirm", "yep": "confirm", "yup": "confirm",
    "correct": "confirm", "right": "confirm",
    "no": "deny", "nope": "deny", "nah": "deny",
    "bye": "goodbye", "goodbye": "goodbye",
    "cancel": "cancel",
    "help": "help",
    "hi": "greeting", "hello": "greeting", "hey": "greeting",
}


def classify(text: str) -> List[Intent]:
    """Return intents ranked by confidence (highest first).

    Always returns at least one intent — `fallback` with confidence 0.0 if
    nothing else matched. The state machine relies on this contract.
    """
    if not text or not text.strip():
        return [Intent("silence", 1.0)]

    raw = text.strip()
    lowered = raw.lower()

    # Fast path: single-token exact match
    bare = re.sub(r"[^\w\s]", "", lowered).strip()
    tokens = bare.split()
    if len(tokens) == 1 and tokens[0] in _FAST_OVERRIDES:
        return [Intent(_FAST_OVERRIDES[tokens[0]], 0.98, raw)]

    candidates: List[Intent] = []
    for intent_name, patterns, base in _RULES:
        best = 0.0
        for pat in patterns:
            # IGNORECASE so patterns with capital I / [A-Z] still match
            # after the input has been lowercased.
            m = re.search(pat, lowered, re.IGNORECASE)
            if m:
                # Bump confidence by matched length so longer matches win ties.
                score = base + min(0.2, len(m.group(0)) / 60.0)
                if score > best:
                    best = score
        if best > 0:
            candidates.append(Intent(intent_name, min(0.99, best), raw))

    if not candidates:
        return [Intent("fallback", 0.05, raw)]

    candidates.sort(key=lambda i: i.confidence, reverse=True)
    return candidates


def top_intent(text: str) -> Intent:
    """Convenience: just the highest-confidence intent."""
    return classify(text)[0]
