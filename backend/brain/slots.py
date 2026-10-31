"""
Slot extraction and normalisation for the Clinic Appointment Voice Agent.

Extraction is deliberately decoupled from intent classification.
The FSM calls extract_slots() only after the intent check — never before.
"""

import re
from datetime import datetime, date, timedelta
from typing import Optional

try:
    import dateparser as _dp
    _DATEPARSER_OK = True
except ImportError:
    _DATEPARSER_OK = False


# ── Doctor registry ───────────────────────────────────────────────────────────

# Doctor aliases requiring "dr" or "doctor"
_DOCTOR_ALIASES: dict[str, str] = {
    "dr khan":      "Dr. Khan",
    "doctor khan":  "Dr. Khan",
    "dr smith":     "Dr. Smith",
    "doctor smith": "Dr. Smith",
    "dr patel":     "Dr. Patel",
    "doctor patel": "Dr. Patel",
    "dr ali":       "Dr. Ali",
    "doctor ali":   "Dr. Ali",
}

# Standalone surname references like "Patel" or "Khan"
_DOCTOR_SURNAMES: dict[str, str] = {
    "khan":  "Dr. Khan",
    "smith": "Dr. Smith",
    "patel": "Dr. Patel",
    "ali":   "Dr. Ali",
}

_ANY_DOCTOR_RE = re.compile(
    r"\b(any|no\s+preference|first\s+available|whoever|anyone|"
    r"don'?t\s+mind|doesn'?t\s+matter|don'?t\s+care)\b",
    re.IGNORECASE,
)

# ── Time fuzzy map ────────────────────────────────────────────────────────────

_TIME_FUZZY: dict[str, str] = {
    "early morning": "08:00",
    "morning":       "09:00",
    "midday":        "12:00",
    "noon":          "12:00",
    "lunchtime":     "12:00",
    "lunch":         "12:00",
    "afternoon":     "14:00",
    "evening":       "17:00",
    "night":         "18:00",
}

# Reason keywords for opportunistic extraction
_REASON_KEYWORDS = [
    "toothache", "tooth ache", "tooth pain",
    "checkup", "check-up", "check up",
    "cleaning", "cavity", "filling", "extraction",
    "root canal", "braces", "consultation",
    r"follow[- ]?up", "routine", "pain", "hurt",
    "bleeding", "swollen", "swelling", "infection",
    "sensitivity", "sensitive", "broken tooth", "chipped",
    "crown", "implant", "whitening",
]

_FILLER_WORDS = {"um", "uh", "er", "ah", "well", "so", "like", "just", "hmm", "actually", "sorry"}
_NAME_FILLER  = {"the", "a", "an", "is", "its", "it", "my", "me", "yes",
                 "no", "ok", "okay", "sure"} | _FILLER_WORDS


# ── Name ─────────────────────────────────────────────────────────────────────

def extract_name(text: str) -> Optional[str]:
    # Strip common leading fillers and corrections
    cleaned_input = re.sub(r"^(?:um|uh|er|ah|well|sorry|oops)[,\s]+", "", text.strip(), flags=re.IGNORECASE)

    patterns = [
        r"(?:my\s+name\s+is(?:\s+actually)?|i'?m(?:\s+actually)?|it'?s(?:\s+actually)?|name'?s(?:\s+actually)?|call\s+me|appointment\s+for|booking\s+for)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)",
    ]
    for pattern in patterns:
        m = re.search(pattern, cleaned_input, re.IGNORECASE)
        if m:
            raw_match = m.group(1).strip()
            first_part = re.split(r"\s+(?:with|on|at|for|about)\s+", raw_match, flags=re.IGNORECASE)[0]
            cleaned = _clean_name(first_part)
            if cleaned and not any(w.lower() in _NAME_FILLER for w in cleaned.split()):
                return cleaned

    # Fallback: 1–3 plain words that look like a proper name
    words = cleaned_input.split()
    if 1 <= len(words) <= 3 and all(re.fullmatch(r"[A-Za-z]+", w) for w in words):
        # Exclude obvious keyboard mash / vowelless gibberish
        for w in words:
            if re.fullmatch(r"(?:asdfghjkl|qwertyuiop|zxcvbnm|xyzzy|blerf|foobar)", w, re.IGNORECASE):
                return None
            if len(w) >= 5 and not re.search(r"[aeiouy]", w, re.IGNORECASE):
                return None

        if not any(w.lower() in _NAME_FILLER for w in words):
            return _clean_name(" ".join(words))

    return None


def _clean_name(raw: str) -> str:
    parts = [w for w in raw.split() if w.lower() not in _FILLER_WORDS]
    return " ".join(w.capitalize() for w in parts) if parts else raw.strip().title()


# ── Doctor ────────────────────────────────────────────────────────────────────

def extract_doctor(text: str) -> Optional[str]:
    t = text.lower().strip()

    if _ANY_DOCTOR_RE.search(t):
        return "any"

    for alias, canonical in _DOCTOR_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", t):
            return canonical

    m = re.search(r"\b(dr\.?|doctor)\s+([a-zA-Z]+)\b", t, re.IGNORECASE)
    if m:
        return f"Dr. {m.group(2).capitalize()}"

    # Only match bare surname if caller just said the surname or "prefer X"
    for surname, canonical in _DOCTOR_SURNAMES.items():
        if re.fullmatch(rf"{surname}", t) or re.search(rf"\b(?:prefer|see|with|choose)\s+{surname}\b", t):
            return canonical

    return None


# ── Date ──────────────────────────────────────────────────────────────────────

def is_past_date(text: str) -> bool:
    """Check if the text refers to a date in the past."""
    t = text.lower().strip()
    base = date.today()

    # Check numeric dates like DD/MM/YYYY or MM/DD/YYYY
    m = re.search(r"\b(\d{1,2})[/\.-](\d{1,2})[/\.-](\d{2,4})\b", t)
    if m:
        n1, n2, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yr < 100:
            yr += 2000
        dates = []
        for mo, day in [(n1, n2), (n2, n1)]:
            try:
                dates.append(date(yr, mo, day))
            except ValueError:
                pass
        # If any valid interpretation is today or in the future, it's not strictly past
        if dates and any(d >= base for d in dates):
            return False
        if dates and all(d < base for d in dates):
            return True

    # Relative past markers
    if re.search(r"\b(yesterday|last\s+(?:week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b", t):
        return True

    if _DATEPARSER_OK:
        res = _dp.parse(text)
        if res and res.date() < base:
            return True

    return False


def extract_date(text: str) -> Optional[str]:
    """
    Parse a date from *text*.
    Returns an ISO-8601 string (YYYY-MM-DD) for future dates (or today),
    None if unparseable or the date is in the past.
    Supports formats like 11/2/26 (Nov 2, 2026), 2/11/2026 (Nov 2, 2026),
    weekday names, relative dates, and ISO dates.
    """
    t = text.lower().strip()
    base = date.today()

    # 1. Numeric date handling with smart slash/dot/dash support
    m = re.search(r"\b(\d{1,2})[/\.-](\d{1,2})[/\.-](\d{2,4})\b", t)
    if m:
        n1, n2, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yr < 100:
            yr += 2000
        candidates = []
        for mo, day in [(n1, n2), (n2, n1)]:
            try:
                d = date(yr, mo, day)
                if d >= base:
                    candidates.append(d)
            except ValueError:
                pass
        if candidates:
            candidates.sort()
            return candidates[0].strftime("%Y-%m-%d")
        return None

    # Check fallback weekday names / relative keywords first if present
    weekday_fallback = _extract_date_fallback(text)
    if weekday_fallback:
        return weekday_fallback

    # Avoid parsing bare times like "3pm" as today's date
    has_date_token = bool(
        re.search(
            r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
            r"january|february|march|april|may|june|july|august|september|"
            r"october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b",
            t,
        )
        or re.search(r"\b\d{1,4}[/\.-]\d{1,2}[/\.-]\d{1,4}\b", t)
        or re.search(r"\b\d{1,2}(st|nd|rd|th)\b", t)
    )

    if _DATEPARSER_OK and has_date_token:
        # First try exact parse
        res = _dp.parse(text)
        if res and res.date() >= base:
            return res.date().strftime("%Y-%m-%d")

        # Then try with future preference within 1 year
        settings = {
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": datetime.now(),
            "RETURN_AS_TIMEZONE_AWARE": False,
        }
        result = _dp.parse(text, settings=settings)
        if result and base <= result.date() <= base + timedelta(days=365):
            return result.date().strftime("%Y-%m-%d")

    return None


def _extract_date_fallback(text: str) -> Optional[str]:
    """Simple regex date parser used when dateparser is not installed."""
    t = text.lower()
    today = date.today()

    if "today" in t:
        return today.strftime("%Y-%m-%d")
    if "tomorrow" in t:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, name in enumerate(day_names):
        if name in t:
            days_ahead = (i - today.weekday()) % 7 or 7
            target = today + timedelta(days=days_ahead)
            return target.strftime("%Y-%m-%d")

    return None


# ── Time ──────────────────────────────────────────────────────────────────────

def extract_time(text: str) -> Optional[str]:
    t = text.lower().strip()

    # e.g. "3pm", "3:30pm", "10 am"
    m = re.search(r"(?:\b|(?<=\d))(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", t, re.IGNORECASE)
    if m:
        hour   = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        meridiem = m.group(3).lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    # Fuzzy words — check longest match first to avoid "morning" inside "early morning"
    for phrase in sorted(_TIME_FUZZY, key=len, reverse=True):
        if re.search(rf"\b{re.escape(phrase)}\b", t):
            return _TIME_FUZZY[phrase]

    # 24-hour "14:30"
    m = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", t)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"

    return None


# ── Reason ────────────────────────────────────────────────────────────────────

def extract_reason(text: str) -> Optional[str]:
    t = text.lower()
    for kw in _REASON_KEYWORDS:
        if re.search(kw, t):
            return re.sub(r"[-?]", " ", kw).strip()
    return None


# ── Composite ─────────────────────────────────────────────────────────────────

def extract_slots(text: str) -> dict:
    """
    Attempt to extract all slot types from *text*.
    Returns a dict containing only the slots that were successfully extracted.
    """
    slots: dict = {}
    if (v := extract_name(text))   is not None: slots["name"]   = v
    if (v := extract_doctor(text)) is not None: slots["doctor"] = v
    if (v := extract_date(text))   is not None: slots["date"]   = v
    if (v := extract_time(text))   is not None: slots["time"]   = v
    if (v := extract_reason(text)) is not None: slots["reason"] = v
    return slots

