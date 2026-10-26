"""High-precision regex rules, run on normalized text before the classifier.

A rule only fires when we are near-certain. Short answers (yes/no/hi/thanks)
must match the *whole* utterance, so "no" never fires inside "know", "now" or
"no, make it Friday" (that last one is a change request for the classifier).
"""

import re
from dataclasses import dataclass

RULE_CONFIDENCE = 0.95


@dataclass(frozen=True)
class RuleMatch:
    intent: str
    pattern: str
    confidence: float = RULE_CONFIDENCE


def _alts(*phrases: str) -> str:
    return "(?:" + "|".join(phrases) + ")"


def _whole(head: str, tail: str = "") -> re.Pattern[str]:
    """Utterance is one or more `head` phrases, optionally followed by `tail` phrases."""
    words = f"{head}|{tail}" if tail else head
    return re.compile(rf"^{head}(?:\s+(?:{words}))*$")


_AFFIRM = _alts(
    "yes", "yeah", "yea", "yep", "yup", "ya", "yah", "yes sir", "sure", "ok", "okay", "k",
    "correct", "right", "that's right", "that is right", "that's correct", "that is correct",
    "absolutely", "definitely", "of course", "alright", "all right", "fine", "perfect",
    "sounds good", "go ahead", "please do", "confirm", "confirmed", "haan", "han", "haanji",
    "ji", "jee", "theek hai", "thik hai", "theek", "bilkul",
)  # fmt: skip
_AFFIRM_TAIL = _alts(
    "please", "thanks", "thank you", "book it", "do it", "that works", "that's fine",
    "that is fine", "go ahead", "sir", "madam",
)  # fmt: skip
_DENY = _alts(
    "no", "nope", "nah", "na", "nahi", "nahin", "ji nahi", "not really", "negative", "wrong",
    "incorrect", "that's wrong", "that is wrong", "that's not right", "that is not right",
    "not correct", "that's incorrect", "not that",
)  # fmt: skip
_DENY_TAIL = _alts("thanks", "thank you", "sir", "madam", "please", "i don't")
_GREET = _alts(
    "hi", "hello", "hey", "hiya", "salam", "salaam", "aoa", "good morning", "good afternoon",
    "good evening", r"a?s+a?la+m+\s?(?:o|u)?\s?(?:a|u)?la(?:i|y)?(?:k|q)u?m",
)  # fmt: skip
_GREET_TAIL = _alts("there", "ji", "sir", "madam", "everyone")
_THANKS = _alts(
    "thanks", "thank you", "thank u", "thankyou", "thx", "shukriya", "bohat shukriya",
    "jazakallah", "much appreciated", "appreciate it", "cheers",
)  # fmt: skip
_THANKS_TAIL = _alts("so much", "very much", "a lot", "ji", "sir", "madam", "again")

# Phrases that would make an emergency keyword *not* an emergency right now.
_NEGATION_BEFORE = re.compile(
    r"\b(?:no|not|non|without|never|had|history of|don't have)\s+(?:\w+\s+)?$"
)

EMERGENCY_PATTERNS = [
    r"chest pain",
    r"heart attack",
    r"(?:can't|cannot|can not|unable to|not able to) breathe?",
    r"(?:difficulty|trouble|problem) breathing",
    r"not breathing",
    r"short(?:ness)? of breath",
    r"bleeding (?:heavily|a lot|badly|won't stop|wont stop|non stop|too much)",
    r"(?:heavy|severe|a lot of) bleeding",
    r"unconscious",
    r"passed out",
    r"fainted",
    r"collapsed",
    r"not (?:responding|waking up)",
    r"stroke",
    r"seizure",
    r"choking",
    r"overdose",
    r"(?:swallowed|drank|took) poison",
    r"poisoned",
    r"suicid\w*",
    r"kill (?:myself|himself|herself)",
    r"ambulance",
    r"emergency",
]
_EMERGENCY = [re.compile(rf"\b{p}\b") for p in EMERGENCY_PATTERNS]

_PERSON = _alts(
    "human", "human being", "person", "real person", "someone", "somebody", "agent", "operator",
    "receptionist", "reception", "representative", "staff", "manager", "front desk",
    "customer service", "customer care", "insaan",
)  # fmt: skip
_ORDERED_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "human_agent",
        re.compile(
            rf"\b(?:talk|speak|connect|transfer|put|get|baat)\b(?:\s+\w+){{0,4}}?\s+{_PERSON}\b"
            rf"|^(?:a\s+)?{_PERSON}(?:\s+please)?$"
            rf"|\btransfer (?:the|my|this) call\b|\binsaan se baat\b"
            rf"|\bdon't want to (?:talk|speak) to a (?:machine|robot|bot|computer)\b"
        ),
    ),
    (
        "abort",
        re.compile(
            r"^(?:ok\s+|okay\s+)?(?:never ?mind|forget (?:it|about it|that)|leave it|rehne do"
            r"|chhoro|stop(?: it| this)?|start (?:over|again)|abort|let's start again)"
            r"(?:\s+(?:please|then|for now|i'll call later|i will call later))*$"
        ),
    ),
    (
        "repeat",
        re.compile(
            r"\b(?:repeat|say (?:that|it) again|come again|one more time|dobara|phir se)\b"
            r"|\bi (?:didn't|did not|couldn't|could not) (?:catch|hear|get|understand)"
            r" (?:that|you|it)\b"
            r"|\bwhat did you say\b"
            r"|^(?:what|huh|sorry|pardon|excuse me|sorry what|what was that|say again)$"
        ),
    ),
    (
        "goodbye",
        re.compile(
            r"\b(?:bye|goodbye|good bye|allah hafiz|khuda hafiz|hang up|end (?:the|this) call)\b"
            r"|^(?:ok\s+|no\s+)?(?:that's all|that is all|that's it|nothing else|nothing more"
            r"|see you(?: later)?|take care|i'm done|that will be all)"
            r"(?:\s+(?:thanks|thank you|for now|bye))*$"
        ),
    ),
    ("thank_you", _whole(_THANKS, _THANKS_TAIL)),
    ("greet", _whole(_GREET, _GREET_TAIL)),
    ("deny", _whole(_DENY, _DENY_TAIL)),
    ("affirm", _whole(_AFFIRM, _AFFIRM_TAIL)),
]


def _match_emergency(text: str) -> RuleMatch | None:
    for pattern in _EMERGENCY:
        for m in pattern.finditer(text):
            if _NEGATION_BEFORE.search(text[: m.start()]):
                continue
            return RuleMatch("emergency", pattern.pattern)
    return None


def match_rules(text: str) -> RuleMatch | None:
    """Return the first rule that fires on normalized ``text``, emergency first."""
    if not text:
        return None
    emergency = _match_emergency(text)
    if emergency:
        return emergency
    for intent, pattern in _ORDERED_RULES:
        if pattern.search(text):
            return RuleMatch(intent, pattern.pattern)
    return None
