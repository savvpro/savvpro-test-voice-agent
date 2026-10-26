
import re
from datetime import date, time, timedelta

from app.brain.nlu import INTENT_PHRASES, SERVICE_PHRASES, normalize

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


def words_to_digits(text: str) -> str:
    """'five' -> '5'. Only used inside extractors, never in normalize()."""
    pattern = r"\b(" + "|".join(NUMBER_WORDS) + r")\b"
    return re.sub(pattern, lambda m: str(NUMBER_WORDS[m.group(1)]), text)


def to_24h(hour: int, am_pm: str | None) -> int:
    """Clinic rule: an explicit am/pm wins; a bare 1-8 means PM; 9-12 stays; 13+ is 24-hour."""
    if am_pm == "am":
        return 0 if hour == 12 else hour
    if am_pm == "pm":
        return hour if hour >= 12 else hour + 12
    if 1 <= hour <= 8:
        return hour + 12
    return hour


def _make_time(hour: int, minute: int) -> time | None:
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return time(hour, minute)
    return None


def detect_time(text: str, expecting: str | None = None) -> time | None:
    t = words_to_digits(normalize(text))

    if re.search(r"\bnoon\b", t):
        return time(12, 0)

    m = re.search(r"\bhalf past (\d{1,2})\b", t)
    if m:
        return _make_time(to_24h(int(m.group(1)), None), 30)

    m = re.search(r"\bquarter past (\d{1,2})\b", t)
    if m:
        return _make_time(to_24h(int(m.group(1)), None), 15)

    m = re.search(r"\bquarter to (\d{1,2})\b", t)
    if m:
        return _make_time(to_24h(int(m.group(1)), None) - 1, 45)

    m = re.search(r"\b(\d{1,2}):(\d{2})\s?(am|pm)?\b", t)
    if m:
        return _make_time(to_24h(int(m.group(1)), m.group(3)), int(m.group(2)))

    m = re.search(r"\b(\d{1,2})\s?(am|pm)\b", t)
    if m:
        return _make_time(to_24h(int(m.group(1)), m.group(2)), 0)

    m = re.search(r"\b(\d{1,2})\s?oclock\b", t)
    if m:
        return _make_time(to_24h(int(m.group(1)), None), 0)

    m = re.search(r"\b(?:at|by|around)\s+(\d{1,2})\b", t)
    if m:
        return _make_time(to_24h(int(m.group(1)), None), 0)

    if expecting == "time":  # the assistant just asked for a time, so "5" means 5 o'clock
        m = re.fullmatch(r"(\d{1,2})", t.strip())
        if m:
            return _make_time(to_24h(int(m.group(1)), None), 0)

    return None


WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
_WEEKDAY_RE = "|".join(WEEKDAYS)


def _build_date(day: int, month: int, year: int | None, today: date) -> date | None:
    try:
        if year is not None:
            return date(year, month, day)
        result = date(today.year, month, day)
        if result < today:  # "3 January" said in October means next year
            result = date(today.year + 1, month, day)
        return result
    except ValueError:  # e.g. 31 February
        return None


def detect_date(text: str, today: date) -> date | None:
    t = normalize(text)

    if re.search(r"\bday after tomorrow\b", t):
        return today + timedelta(days=2)
    if re.search(r"\b(tomorrow|tmrw|tommorow)\b", t):
        return today + timedelta(days=1)
    if re.search(r"\b(today|tonight)\b", t):
        return today

    m = re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_RE})(?:\s+(20\d{{2}}))?\b", t
    )
    if m:
        year = int(m.group(3)) if m.group(3) else None
        return _build_date(int(m.group(1)), MONTHS[m.group(2)], year, today)

    m = re.search(
        rf"\b({_MONTH_RE})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+(20\d{{2}}))?\b", t
    )
    if m:
        year = int(m.group(3)) if m.group(3) else None
        return _build_date(int(m.group(2)), MONTHS[m.group(1)], year, today)

    m = re.search(rf"\b({_WEEKDAY_RE})\b", t)
    if m:

        delta = (WEEKDAYS[m.group(1)] - today.weekday()) % 7
        return today + timedelta(days=delta or 7)

    return None


DIGIT_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}


def detect_phone(text: str) -> str | None:
    t = normalize(text)
    pattern = r"\b(" + "|".join(DIGIT_WORDS) + r")\b"
    t = re.sub(pattern, lambda m: DIGIT_WORDS[m.group(1)], t)
    # digits that may be separated by single spaces ("0312 345 6789" or "0 3 1 2 ...")
    for m in re.finditer(r"(?<!\d)(?:\d ?){10,13}(?!\d)", t):
        digits = re.sub(r"\D", "", m.group(0))
        if 10 <= len(digits) <= 13:
            return digits
    return None

RELATIONS = {
    "mother": "mother", "mom": "mother", "mum": "mother", "mama": "mother",
    "father": "father", "dad": "father", "papa": "father",
    "wife": "wife", "husband": "husband", "son": "son", "daughter": "daughter",
    "brother": "brother", "sister": "sister", "friend": "friend",
    "child": "child", "kid": "child", "baby": "child",
    "grandmother": "grandmother", "grandfather": "grandfather",
}

_FILLER_WORDS = {
    "its", "it", "is", "for", "my", "her", "his", "the", "name", "patient",
    "me", "myself", "i", "am", "im", "this", "thats", "called", "named",
    "please", "and", "of", "mr", "mrs", "ms", "miss", "dr",
} | set(RELATIONS)

_COMMON_WORDS = {
    "what", "when", "where", "why", "how", "who", "which", "are", "you", "your",
    "can", "could", "would", "do", "does", "did", "have", "has", "will", "to",
    "in", "on", "at", "a", "an", "with", "from", "about", "age", "aged", "old",
    "year", "years", "phone", "number", "call", "calling", "today", "tomorrow",
    "tonight", "good", "great", "sorry", "thanks", "thank", "not", "just",
    "that", "there", "here", "need", "want", "like", "looking", "trying",
    "available", "free", "busy", "sure", "fine", "okay", "ok", "yes", "no",
    "have", "get", "make", "take", "see", "come", "go", "be", "so", "but", "or",
}


def _build_not_names() -> set[str]:
    words: set[str] = set(_COMMON_WORDS) | set(WEEKDAYS) | set(MONTHS) | set(NUMBER_WORDS)
    for phrases in list(INTENT_PHRASES.values()) + list(SERVICE_PHRASES.values()):
        for phrase in phrases:
            words.update(phrase.split())
    return words


NOT_NAMES = _build_not_names()

_EXPLICIT_NAME = re.compile(
    r"\b(?:my name is|name is|names|called|named|patient is|patient name is|"
    r"this is|i am|im)\s+([a-z]+(?:\s+[a-z]+){0,2})"
)


def _clean_name(tokens: list[str]) -> str | None:
    """Keep leading name-like words (max 3); stop at the first word that is not a name."""
    kept: list[str] = []
    for token in tokens:
        if not token.isalpha() or token in NOT_NAMES or token in _FILLER_WORDS:
            break
        kept.append(token)
        if len(kept) == 3:
            break
    if not kept:
        return None
    return " ".join(word.capitalize() for word in kept)


def detect_name(text: str, expecting: str | None = None) -> str | None:
    t = normalize(text)

    m = _EXPLICIT_NAME.search(t)
    if m:
        name = _clean_name(m.group(1).split())
        if name:
            return name

    if expecting == "name":
        tokens = [w for w in t.split() if w not in _FILLER_WORDS]
        if 1 <= len(tokens) <= 3 and all(
            w.isalpha() and w not in NOT_NAMES for w in tokens
        ):
            return " ".join(w.capitalize() for w in tokens)

    return None


_ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3}


def detect_choice(text: str) -> int | None:
    t = normalize(text)
    m = re.search(r"\b(first|1st|second|2nd|third|3rd)\b", t)
    if m:
        return _ORDINALS[m.group(1)]
    m = re.search(r"\b(?:option|number|choice)\s+(\d)\b", t)
    if m:
        return int(m.group(1))
    return None


_RELATION_RE = re.compile(r"\b(?:my|his|her)\s+(" + "|".join(RELATIONS) + r")\b")


def detect_relation(text: str) -> str | None:
    m = _RELATION_RE.search(normalize(text))
    return RELATIONS[m.group(1)] if m else None
