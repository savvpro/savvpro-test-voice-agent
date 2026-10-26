"""RapidFuzz matchers: tolerate STT spelling ("cardio logy", "dermatolagy").

Scores are 0..1. Exact word matches always win over fuzzy ones, and short
vocabulary (ent, gp, bp, ear) must match exactly — fuzzy matching three-letter
words produces nonsense.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz

from app.nlu.lexicon import load_lexicon

DEPARTMENT_THRESHOLD = 85
# After "dr"/"doctor" one wrong letter in a 5-letter name (score 80) is accepted;
# after the weaker "with" it is not ("with usama" is not Dr. Saima).
DOCTOR_THRESHOLD = 80
DOCTOR_WEAK_TRIGGER_THRESHOLD = 85
FULL_NAME_THRESHOLD = 90
MIN_FUZZY_LENGTH = 5
SYMPTOM_WEIGHT = 0.9  # "fever" hints at General Medicine less strongly than "physician"

_NEGATED_BEFORE = re.compile(
    r"\b(?:not|no|instead of|rather than|from|except|other than)\s+(?:the\s+)?$"
)


@dataclass(frozen=True)
class FuzzyMatch:
    value: str
    score: float
    matched: str


def preceded_by_negation(text: str, start: int) -> bool:
    """True for the 'monday' in 'not monday' / 'instead of monday' / 'from monday'."""
    return bool(_NEGATED_BEFORE.search(text[:start]))


def _ngrams(tokens: list[str], sizes: range) -> list[tuple[str, int]]:
    """(phrase, char offset) for every n-gram of the given sizes."""
    offsets = []
    pos = 0
    for tok in tokens:
        offsets.append(pos)
        pos += len(tok) + 1
    grams = []
    for n in sizes:
        for i in range(len(tokens) - n + 1):
            grams.append((" ".join(tokens[i : i + n]), offsets[i]))
    return grams


@lru_cache
def _department_vocabulary() -> list[tuple[str, str, float]]:
    vocab = []
    for department, entry in load_lexicon()["departments"].items():
        vocab += [(p, department, 1.0) for p in entry["synonyms"]]
        vocab += [(p, department, SYMPTOM_WEIGHT) for p in entry["symptoms"]]
    return vocab


def match_department(text: str) -> FuzzyMatch | None:
    """Best department mentioned in normalized ``text``.

    Ranking: score, then the more specific (longer) phrase, then earliest position.
    """
    tokens = text.split()
    best: tuple[float, int, int, FuzzyMatch] | None = None
    for phrase, department, weight in _department_vocabulary():
        found = _find_phrase(text, tokens, phrase)
        if found is None:
            continue
        raw_score, position, matched = found
        if preceded_by_negation(text, position):
            continue
        score = raw_score * weight
        key = (score, len(phrase), -position, FuzzyMatch(department, round(score, 3), matched))
        if best is None or key[:3] > best[:3]:
            best = key
    return best[3] if best else None


def _find_phrase(text: str, tokens: list[str], phrase: str) -> tuple[float, int, str] | None:
    exact = re.search(rf"\b{re.escape(phrase)}\b", text)
    if exact:
        return 1.0, exact.start(), phrase
    squashed = phrase.replace(" ", "")
    if len(squashed) < MIN_FUZZY_LENGTH:
        return None
    n = len(phrase.split())
    best: tuple[float, int, str] | None = None
    for gram, position in _ngrams(tokens, range(max(1, n - 1), n + 2)):
        score = fuzz.ratio(squashed, gram.replace(" ", ""))
        if score >= DEPARTMENT_THRESHOLD and (best is None or score / 100 > best[0]):
            best = (score / 100, position, gram)
    return best


def match_unknown_department(text: str) -> FuzzyMatch | None:
    """A specialty the clinic does not offer ("dentist", "eye doctor")."""
    for phrase in sorted(load_lexicon()["unknown_departments"], key=len, reverse=True):
        m = re.search(rf"\b{re.escape(phrase)}s?\b", text)
        if m:
            return FuzzyMatch(phrase, 1.0, m.group())
    return None


def _strip_title(name: str) -> str:
    return re.sub(r"^(?:dr\.?|doctor)\s+", "", name.lower()).strip()


def match_doctor(text: str, doctor_names: Sequence[str]) -> FuzzyMatch | None:
    """Doctor referred to as "dr saima", "doctor rauf", "with imran haider", or by full name.

    A bare first name is not enough ("my name is bilal" is a patient), so a
    single name needs a trigger word (dr/doctor/with) in front of it.
    """
    people = [(full, _strip_title(full)) for full in doctor_names]
    best: FuzzyMatch | None = None

    def consider(candidate: FuzzyMatch) -> None:
        nonlocal best
        if best is None or candidate.score > best.score:
            best = candidate

    trigger = r"\b(?:with\s+)?(dr|doctor|doc|with)\s+([a-z]+)(?:\s+([a-z]+))?"
    for m in re.finditer(trigger, text):
        title, first, second = m.groups()
        threshold = DOCTOR_WEAK_TRIGGER_THRESHOLD if title == "with" else DOCTOR_THRESHOLD
        for full, plain in people:
            if second:
                score = fuzz.ratio(f"{first} {second}", plain)
                if score >= threshold:
                    consider(FuzzyMatch(full, score / 100, f"{first} {second}"))
                    continue
            if len(first) >= 4:
                score = max(fuzz.ratio(first, part) for part in plain.split())
                if score >= threshold:
                    consider(FuzzyMatch(full, score / 100, first))

    tokens = text.split()
    for gram, _ in _ngrams(tokens, range(2, 3)):
        for full, plain in people:
            score = fuzz.ratio(gram, plain)
            if score >= FULL_NAME_THRESHOLD:
                consider(FuzzyMatch(full, score / 100, gram))
    return best


@lru_cache
def _intent_keywords() -> dict[str, list[str]]:
    return load_lexicon()["intent_keywords"]


def match_intent_keywords(text: str) -> list[tuple[str, float]]:
    """Fallback intent scores (token_set_ratio vs keyword phrases), best first."""
    if not text:
        return []
    scores = [
        (intent, max(fuzz.token_set_ratio(text, phrase) for phrase in phrases) / 100)
        for intent, phrases in _intent_keywords().items()
    ]
    return sorted(scores, key=lambda item: item[1], reverse=True)
