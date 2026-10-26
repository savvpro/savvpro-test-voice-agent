"""What the caller wants, and the details they mentioned.

Intents are matched with weighted keyword patterns, so every decision has a
reason and a score; nothing is guessed by a model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# intent -> list of (pattern, weight)
INTENT_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "book": [(r"\b(book|schedule|make|set up|need|want|get)\b.*\b(appointment|visit|cleaning|checkup|check up|exam)\b", 0.9),
             (r"\b(appointment|cleaning|checkup|check up|see (the )?dentist|come in)\b", 0.6),
             (r"\bbook\b", 0.7)],
    "reschedule": [(r"\b(reschedule|move|change|push back|postpone)\b.*\b(appointment|booking|visit)\b", 0.95),
                   (r"\breschedule\b", 0.9)],
    "cancel_appointment": [(r"\bcancel\b.*\b(appointment|booking|visit)\b", 0.95),
                           (r"\bcancel (it|my)\b", 0.8)],
    "emergency": [(r"\b(emergency|severe pain|really bad pain|unbearable|swollen|swelling|bleeding|knocked out|broke(n)? (a |my )?tooth|abscess)\b", 0.95),
                  (r"\b(toothache|tooth ache|hurts? (a lot|so much)|in pain)\b", 0.8)],
    "hours": [(r"\b(hours|open|close|closing|opening)\b", 0.8)],
    "location": [(r"\b(where are you|address|located|location|directions|parking)\b", 0.85)],
    "insurance": [(r"\b(insurance|delta|cigna|aetna|metlife|guardian|cost|price|how much)\b", 0.8)],
    "repeat": [(r"\b(repeat|say that again|didn'?t (catch|hear)|pardon|come again)\b", 0.9)],
    "restart": [(r"\b(start over|start again|restart|from the beginning)\b", 0.9)],
    "human": [(r"\b(human|real person|receptionist|front desk|operator|speak to (someone|somebody))\b", 0.9)],
    "goodbye": [(r"\b(bye|goodbye|that'?s all|nothing else|no thanks|hang up)\b", 0.85)],
    "affirm": [(r"^(yes|yeah|yep|yup|sure|correct|right|ok|okay|perfect|sounds good|that works|great|please do|do it|go ahead|absolutely|confirm)\b", 0.9),
               (r"\b(yes|yeah|that works|sounds good|perfect|correct)\b", 0.7)],
    "deny": [(r"^(no|nope|nah|not really|wrong|that'?s not right|incorrect)\b", 0.9),
             (r"\b(no wait|actually|instead|not that)\b", 0.6)],
}

SERVICES = {
    "cleaning": r"\b(clean(ing)?|hygiene|polish)\b",
    "checkup": r"\b(check ?up|exam|examination|x-?rays?)\b",
    "filling": r"\b(filling|cavity|cavities)\b",
    "whitening": r"\b(whiten(ing)?|bleach(ing)?)\b",
    "consultation": r"\b(consult(ation)?|implant|crown|veneer|braces|invisalign)\b",
    "emergency": r"\b(emergency|pain|toothache|swollen|swelling|bleeding|broke(n)?)\b",
}


@dataclass
class Understanding:
    intent: str | None
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)
    service: str | None = None
    name: str | None = None
    phone: str | None = None
    choice: int | None = None  # "the first one" / "the second one"
    correction: bool = False  # "no wait", "actually", "instead"


def classify(text: str) -> tuple[str | None, float, dict[str, float]]:
    scores: dict[str, float] = {}
    for intent, patterns in INTENT_PATTERNS.items():
        best = max((w for p, w in patterns if re.search(p, text)), default=0.0)
        if best:
            scores[intent] = best
    if not scores:
        return None, 0.0, {}
    intent = max(scores, key=scores.get)
    return intent, scores[intent], scores


def find_service(text: str) -> str | None:
    for service, pattern in SERVICES.items():
        if re.search(pattern, text):
            return service
    return None


def find_name(text: str) -> str | None:
    m = re.search(r"\b(?:my name is|name'?s|this is|i'?m|i am|it'?s)\s+([a-z][a-z'-]+(?:\s+[a-z][a-z'-]+)?)", text)
    if not m:
        return None
    words = [w for w in m.group(1).split() if w not in _NOT_NAMES]
    return " ".join(w.capitalize() for w in words) or None


_NOT_NAMES = {"calling", "looking", "trying", "here", "the", "a", "in", "not", "just", "fine", "good",
              "free", "available", "sure", "okay", "busy", "booked", "wondering", "going", "at", "on", "for"}


def find_phone(text: str) -> str | None:
    # Any number the caller gives, in any grouping ("135 567454 2132",
    # "+44 20 7946 0000"): one run of 7 to 15 digits with spaces, dots, dashes
    # or brackets between them. Looking at one run at a time keeps
    # "tomorrow at 10 am, 555 222 3333" from gluing the 10 onto the number.
    for run in re.findall(r"\+?\(?\d[\d\s().-]*\d", text):
        digits = re.sub(r"\D", "", run)
        if 7 <= len(digits) <= 15:
            return digits
    return None


def wants_to_skip(text: str) -> bool:
    """The caller would rather not give a phone number."""
    return bool(re.search(
        r"^(no|nope|nah)\b|\b(skip|rather not|prefer not|don'?t (want|have)|no (phone|number)|"
        r"not (giving|sharing)|leave it|no thanks|without)\b", text))


def find_choice(text: str) -> int | None:
    if re.search(r"\b(1th|1st|first|earlier|earliest)\b", text):
        return 1
    if re.search(r"\b(2th|2nd|second|later|latest|other one|last one)\b", text):
        return 2
    return None


def understand(text: str) -> Understanding:
    intent, confidence, scores = classify(text)
    return Understanding(
        intent=intent,
        confidence=confidence,
        scores=scores,
        service=find_service(text),
        name=find_name(text),
        phone=find_phone(text),
        choice=find_choice(text),
        correction=bool(re.search(r"\b(no wait|actually|instead|make (it|that)|change (it|that) to|rather)\b", text)),
    )
