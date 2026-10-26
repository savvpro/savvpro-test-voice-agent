"""Intent parser — extracts user intents and entities using regex and keywords.

No LLM or external AI service is used. All parsing is deterministic,
based on pattern matching, keyword lookup, and explicit rules.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.brain.states import Intent

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

NUMBER_WORDS: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

DAY_NAMES: dict[str, int] = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

DAY_ABBREVIATIONS: dict[str, int] = {
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3,
    "thurs": 3, "fri": 4, "sat": 5, "sun": 6,
}

MONTH_NAMES: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

MONTH_ABBREVIATIONS: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}

# Merge full + abbreviated lookups for convenience
ALL_DAYS: dict[str, int] = {**DAY_NAMES, **DAY_ABBREVIATIONS}
ALL_MONTHS: dict[str, int] = {**MONTH_NAMES, **MONTH_ABBREVIATIONS}

# ---------------------------------------------------------------------------
# Parse result
# ---------------------------------------------------------------------------


@dataclass
class ParseResult:
    """Result of parsing a single user utterance."""

    intent: Intent = Intent.UNKNOWN
    date: Optional[str] = None       # ISO format YYYY-MM-DD
    time: Optional[str] = None       # 24-h format HH:MM
    party_size: Optional[int] = None
    raw_number: Optional[int] = None  # bare number needing context
    raw_text: str = ""
    date_error: Optional[str] = None  # "invalid" or "ambiguous"
    time_error: Optional[str] = None  # "invalid" or "ambiguous"


# ---------------------------------------------------------------------------
# Intent parser
# ---------------------------------------------------------------------------


class IntentParser:
    """Deterministic intent and entity parser using regex / keywords."""

    # -- Intent keyword patterns (compiled once) ----------------------------

    _GREETING_RE = re.compile(
        r"\b(hi|hello|hey|howdy|greetings|good\s*(morning|afternoon|evening|day)|"
        r"what'?s\s*up|sup)\b", re.I,
    )
    _CONFIRM_RE = re.compile(
        r"\b(yes|yeah|yep|yup|sure|correct|right|absolutely|definitely|"
        r"confirm|confirmed|ok(?:ay)?|sounds?\s*good|perfect|great|"
        r"that'?s\s*right|book\s*it|go\s*ahead|please\s*book|do\s*it)\b", re.I,
    )
    _DENY_RE = re.compile(
        r"\b(no|nope|nah|wrong|incorrect|that'?s\s*wrong|"
        r"don'?t\s*(book|confirm|think)|do\s+not\s+(book|confirm|think)|"
        r"not\s+(?:quite\s+)?(right|correct|sure|ok(?:ay)?|confirmed)|not\s+yet)\b", re.I,
    )
    _CANCEL_RE = re.compile(
        r"\b(cancel|stop|quit|exit|bye|goodbye|good\s*bye|never\s*mind|"
        r"forget\s*it|end|i'?m\s*done)\b", re.I,
    )
    _RESTART_RE = re.compile(
        r"\b(restart|start\s*over|reset|begin\s*again|new\s*reservation|"
        r"from\s*(the\s*)?(start|beginning|top|scratch))\b", re.I,
    )
    _HELP_RE = re.compile(
        r"\b(help|what\s*can\s*you\s*do|options|menu|commands|"
        r"how\s*does\s*this\s*work|what\s*do\s*you\s*do)\b", re.I,
    )
    _CHANGE_DATE_RE = re.compile(
        r"\b(change|update|modify|different|another|other)\s*(the\s*)?"
        r"(date|day)\b", re.I,
    )
    _CHANGE_TIME_RE = re.compile(
        r"\b(change|update|modify|different|another|other)\s*(the\s*)?"
        r"(time|hour)\b", re.I,
    )
    _CHANGE_PARTY_RE = re.compile(
        r"\b(change|update|modify|different|another|other)\s*(the\s*)?"
        r"(party\s*size|number\s*of\s*(people|guests|persons)|group\s*size|"
        r"head\s*count|size|guests?|people|persons?)\b"
        r"|\b(more|fewer|less)\s*(people|guests|persons)\b", re.I,
    )

    # -- Public API ---------------------------------------------------------

    def parse(
        self, text: str, reference_date: Optional[datetime] = None,
    ) -> ParseResult:
        """Parse user text into an intent and optional entities.

        Parameters
        ----------
        text:
            Raw user utterance.
        reference_date:
            Anchor for relative dates (defaults to *now*). Pass a fixed
            value in tests for deterministic results.
        """
        if not text or not text.strip():
            return ParseResult(intent=Intent.UNKNOWN, raw_text=text or "")

        cleaned = text.strip()
        lower = cleaned.lower().replace("\u2019", "'").replace("\u2212", "-")
        ref = reference_date or datetime.now()

        date, date_error = self._extract_date(lower, ref)
        time, time_error = self._extract_time(lower)
        party_size = self._extract_party_size(lower)
        raw_number = (
            None if date_error or time_error
            else self._extract_raw_number(lower, date, time, party_size)
        )
        intent = self._detect_intent(lower, date, time, party_size, raw_number)

        return ParseResult(
            intent=intent,
            date=date,
            time=time,
            party_size=party_size,
            raw_number=raw_number,
            raw_text=cleaned,
            date_error=date_error,
            time_error=time_error,
        )

    # -- Intent detection ---------------------------------------------------

    def _detect_intent(
        self,
        text: str,
        date: Optional[str],
        time: Optional[str],
        party_size: Optional[int],
        raw_number: Optional[int],
    ) -> Intent:
        """Determine the primary intent from the text and extracted entities."""

        # Global commands and changes take precedence. Entities are applied
        # before confirmation; explicit rejection always wins over affirmation.
        if self._CANCEL_RE.search(text):
            return Intent.CANCEL
        if self._RESTART_RE.search(text):
            return Intent.RESTART
        if self._HELP_RE.search(text):
            return Intent.HELP

        # Change-specific intents
        if self._CHANGE_DATE_RE.search(text):
            return Intent.CHANGE_DATE
        if self._CHANGE_TIME_RE.search(text):
            return Intent.CHANGE_TIME
        if self._CHANGE_PARTY_RE.search(text):
            return Intent.CHANGE_PARTY_SIZE

        # If entities were extracted the user is providing info
        if any(v is not None for v in (date, time, party_size, raw_number)):
            return Intent.PROVIDE_INFO

        # Confirm / deny (checked after entity extraction so that
        # "yes, for 4 people" is PROVIDE_INFO, not just CONFIRM)
        if self._DENY_RE.search(text):
            return Intent.DENY
        if self._CONFIRM_RE.search(text):
            return Intent.CONFIRM

        if self._GREETING_RE.search(text):
            return Intent.GREETING

        return Intent.UNKNOWN

    # -- Date extraction ----------------------------------------------------

    def _extract_date(
        self, text: str, ref: datetime,
    ) -> tuple[Optional[str], Optional[str]]:
        """Return a date and an explicit error for recognised impossible dates.

        A recognised date is consumed as a whole. Its day must never become
        a context-dependent bare number when calendar validation fails.
        """
        today = ref.replace(hour=0, minute=0, second=0, microsecond=0)

        # Explicit years are preserved, including past years.
        match = re.search(r"(?<![\w/-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\w/-])", text)
        if match:
            year, month, day = map(int, match.groups())
            return self._calendar_date(today, month, day, year)

        months = "|".join(ALL_MONTHS)
        named_patterns = (
            rf"\b({months})\s+(\d+)(?:st|nd|rd|th)?\b(?:[,]?\s+(\d{{4}})\b)?",
            rf"\b(\d+)(?:st|nd|rd|th)?\s+(?:of\s+)?({months})\b(?:[,]?\s+(\d{{4}})\b)?",
        )
        for index, pattern in enumerate(named_patterns):
            match = re.search(pattern, text)
            if match:
                if index == 0:
                    month_name, day, year = match.groups()
                else:
                    day, month_name, year = match.groups()
                return self._calendar_date(
                    today, ALL_MONTHS[month_name], int(day), int(year) if year else None,
                )

        # Numeric dates use the existing MM/DD convention, optionally with year.
        match = re.search(
            r"(?<![\w/-])(\d{1,2})([/\-])(\d{1,2})(?:\2(\d{4}))?(?![\w/-])", text,
        )
        if match:
            month, _, day, year = match.groups()
            return self._calendar_date(today, int(month), int(day), int(year) if year else None)

        offsets = (
            (r"\bday\s+after\s+tomorrow\b", 2),
            (r"\byesterday\b", -1),
            (r"\btoday\b", 0),
            (r"\btomorrow\b", 1),
        )
        for pattern, offset in offsets:
            if re.search(pattern, text):
                return (today + timedelta(days=offset)).strftime("%Y-%m-%d"), None

        # Retain the established weekday rules for existing conversations.
        for day_name, day_num in ALL_DAYS.items():
            if re.search(rf"\bnext\s+{day_name}\b", text):
                days_ahead = (day_num - today.weekday()) % 7 or 7
                return (today + timedelta(days=days_ahead + 7)).strftime("%Y-%m-%d"), None
        for day_name, day_num in ALL_DAYS.items():
            if re.search(rf"\b(this\s+)?{day_name}\b", text):
                days_ahead = (day_num - today.weekday()) % 7 or 7
                return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d"), None

        match = re.search(r"\bthe\s+(\d+)\s*(?:st|nd|rd|th)\b", text)
        if match:
            resolved = self._resolve_day_only(today, int(match.group(1)))
            return resolved, None if resolved else "invalid"
        return None, None

    @staticmethod
    def _calendar_date(
        today: datetime, month: int, day: int, year: Optional[int] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        if year is None:
            resolved = IntentParser._resolve_month_day(today, month, day)
            return resolved, None if resolved else "invalid"
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d"), None
        except ValueError:
            return None, "invalid"

    # -- Time extraction ----------------------------------------------------

    def _extract_time(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Validate complete time tokens before choosing a single value.

        One numeric expression handles both clocks and AM/PM times so a
        malformed clock cannot be reinterpreted as its valid suffix.
        """
        candidates: list[str] = []
        invalid = False
        numeric = re.compile(
            r"(?<![\w:])([+-]?\d+)(?:\s*:\s*([+-]?\d+(?:\s*:\s*[+-]?\d+)*))?\s*"
            r"(am|pm|a\.m\.?|p\.m\.?)?(?!\w)", re.I,
        )
        for match in numeric.finditer(text):
            hour_text, minute_text, period = match.groups()
            if minute_text is None and period is None:
                continue  # A date or guest count is not a time token.
            hour = int(hour_text)
            if (
                hour_text.startswith(("-", "+"))
                or (minute_text is not None and re.fullmatch(r"\d{2}", minute_text) is None)
            ):
                invalid = True
                continue
            minute = int(minute_text) if minute_text is not None else 0
            if period:
                value = self._to_24h(hour, minute, period)
            elif 0 <= hour <= 23 and 0 <= minute <= 59:
                value = f"{hour:02d}:{minute:02d}"
            else:
                value = None
            if value is None:
                invalid = True
            else:
                candidates.append(value)

        for _ in re.finditer(r"\b(noon|midday)\b", text):
            candidates.append("12:00")

        words = "|".join(NUMBER_WORDS)
        # Written clock phrases preserve the established PM assumption.
        written = re.compile(
            rf"(?<![\w.+-])({words}|[+-]?\d+)\s+(thirty|fifteen|forty[\s-]?five|o['\u2019]?\s*clock)\b"
            rf"|\bhalf\s+past\s+({words}|[+-]?\d+)\b",
        )
        for match in written.finditer(text):
            hour_text, minute_text, half_hour = match.groups()
            hour_text = half_hour or hour_text
            hour = NUMBER_WORDS[hour_text] if hour_text in NUMBER_WORDS else int(hour_text)
            if not 1 <= hour <= 23:
                invalid = True
                continue
            if 1 <= hour <= 11:
                hour += 12
            minute_text = (minute_text or "thirty").replace("-", " ")
            minute = {"thirty": 30, "fifteen": 15, "forty five": 45, "fortyfive": 45}.get(minute_text, 0)
            candidates.append(f"{hour:02d}:{minute:02d}")

        if invalid:
            return None, "invalid"
        if len(set(candidates)) > 1:
            return None, "ambiguous"
        return (candidates[0], None) if candidates else (None, None)

    # -- Party-size extraction ----------------------------------------------

    def _extract_party_size(self, text: str) -> Optional[int]:
        """Extract the number of guests from text, or None."""

        # "just me", "myself", "alone"
        if re.search(r"\b(just\s*me|myself|alone|only\s*me|solo)\b", text):
            return 1

        # "a couple", "us two"
        if re.search(r"\b(a\s+couple|couple\s+of\s+us|us\s+two|two\s+of\s+us)\b", text):
            return 2

        # "<N> people / guests / persons / pax"
        m = re.search(r"(?<![\w.+-])([+-]?\d+)\s*(people|guests?|persons?|pax|diners?)\b", text)
        if m:
            return int(m.group(1))

        # "for <N>"  / "table for <N>" / "party of <N>" / "group of <N>"
        months = "|".join(ALL_MONTHS)
        m = re.search(
            r"\b(?:for|of)\s+([+-]?\d+)(?![\w./:\d-])"
            rf"(?!\s*(?:am|pm|a\.m|p\.m)\b|\s+(?:of\s+)?(?:{months})\b)", text,
        )
        if m:
            return int(m.group(1))

        # "<N> of us"
        m = re.search(r"(?<![\w.+-])([+-]?\d+)\s+of\s+us\b", text)
        if m:
            return int(m.group(1))

        # Word-number variants: "four people", "for three"
        for word, num in NUMBER_WORDS.items():
            if re.search(
                rf"\b{word}\s*(people|guests?|persons?|pax|diners?)\b", text,
            ):
                return num
            if re.search(rf"\b(?:for|of)\s+{word}\b", text):
                return num
            if re.search(rf"\b{word}\s+of\s+us\b", text):
                return num

        return None

    # -- Raw-number extraction (fallback) -----------------------------------

    def _extract_raw_number(
        self,
        text: str,
        date: Optional[str],
        time: Optional[str],
        party_size: Optional[int],
    ) -> Optional[int]:
        """If a bare number is present and wasn't captured by a specific
        extractor, return it so the engine can interpret using context."""
        if date is not None or time is not None or party_size is not None:
            return None  # a specific extractor already matched

        # Restrict fallback to a complete contextual reply, never a number
        # embedded in unrelated prose or a malformed date/time expression.
        match = re.fullmatch(
            r"(?:actually\s*[, ]*|make\s+it\s+|at\s+|"
            r"(?:change|update|modify)\s+(?:the\s+)?"
            r"(?:date|day|time|hour|party\s*size|number\s+of\s+(?:people|guests|persons)|"
            r"group\s*size|head\s*count|size|guests?|people|persons?)\s+to\s+)?"
            r"([+-]?\d+|"
            + "|".join(NUMBER_WORDS) + r")(?:\s+please)?[.!?]?", text,
        )
        if match:
            value = match.group(1)
            return NUMBER_WORDS[value] if value in NUMBER_WORDS else int(value)
        return None

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _to_24h(hour: int, minute: int, period: str) -> Optional[str]:
        if not 1 <= hour <= 12 or not 0 <= minute <= 59:
            return None
        p = period.lower().replace(".", "").strip()
        if p.startswith("p") and hour != 12:
            hour += 12
        elif p.startswith("a") and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
        return None

    @staticmethod
    def _resolve_month_day(
        today: datetime, month: int, day: int,
    ) -> Optional[str]:
        """Build a date from month+day, rolling to next year if in the past."""
        try:
            candidate = today.replace(month=month, day=day)
        except ValueError:
            return None
        if candidate < today:
            try:
                candidate = candidate.replace(year=candidate.year + 1)
            except ValueError:
                return None
        return candidate.strftime("%Y-%m-%d")

    @staticmethod
    def _resolve_day_only(today: datetime, day: int) -> Optional[str]:
        """Resolve an ordinal day (e.g. 'the 5th') to the nearest future date."""
        try:
            candidate = today.replace(day=day)
        except ValueError:
            return None
        if candidate <= today:
            month = candidate.month + 1
            year = candidate.year
            if month > 12:
                month = 1
                year += 1
            try:
                candidate = candidate.replace(year=year, month=month, day=day)
            except ValueError:
                return None
        return candidate.strftime("%Y-%m-%d")
