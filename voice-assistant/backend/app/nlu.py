"""Deterministic clinic intent and appointment-detail extraction."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

NUMBER_WORDS = {
    "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60,
}
WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thur": 3,
    "thurs": 3, "friday": 4, "fri": 4, "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}
MONTHS = {
    name: index for index, names in enumerate((
        (), ("january", "jan"), ("february", "feb"), ("march", "mar"),
        ("april", "apr"), ("may",), ("june", "jun"), ("july", "jul"),
        ("august", "aug"), ("september", "sep", "sept"),
        ("october", "oct"), ("november", "nov"), ("december", "dec"),
    )) for name in names
}
_MONTH_RX = "|".join(sorted(MONTHS, key=len, reverse=True))
_WEEKDAY_RX = "|".join(sorted(WEEKDAYS, key=len, reverse=True))


def normalize(text: str) -> str:
    value = (text or "")[:2000].lower().replace("\u2019", "'")
    value = re.sub(r"[^a-z0-9:/+' .,@_-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def numberize(text: str) -> str:
    words = text.split()
    result: list[str] = []
    index = 0
    while index < len(words):
        word = words[index]
        if word in NUMBER_WORDS and NUMBER_WORDS[word] >= 20:
            number = NUMBER_WORDS[word]
            if index + 1 < len(words) and NUMBER_WORDS.get(words[index + 1], 0) in range(1, 10):
                number += NUMBER_WORDS[words[index + 1]]
                index += 1
            result.append(str(number))
        else:
            result.append(str(NUMBER_WORDS[word]) if word in NUMBER_WORDS else word)
        index += 1
    return " ".join(result)


def extract_date(text: str, today: date) -> tuple[Optional[date], Optional[str]]:
    month_names = _MONTH_RX
    match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if match:
        year, month, day = map(int, match.groups())
        return _make_date(year, month, day)
    match = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({month_names})\b(?:\s+(\d{{4}}))?", text)
    if match:
        day, month, year = match.groups()
        return _make_date(int(year or today.year), MONTHS[month], int(day), year is None, today)
    match = re.search(rf"\b({month_names})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:\s+(\d{{4}}))?", text)
    if match:
        month, day, year = match.groups()
        return _make_date(int(year or today.year), MONTHS[month], int(day), year is None, today)
    match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
    if match:
        day, month, year = match.groups()
        day, month = int(day), int(month)
        if month > 12 >= day:
            day, month = month, day
        return _make_date(int(year or today.year), month, day, year is None, today)
    if re.search(r"\bday after tomorrow\b|\bin two days\b", text):
        return today + timedelta(days=2), None
    if re.search(r"\btomorrow\b", text):
        return today + timedelta(days=1), None
    if re.search(r"\btoday\b", text):
        return today, None
    match = re.search(rf"\b(?:(next|this|coming) )?({_WEEKDAY_RX})\b", text)
    if match:
        modifier, weekday = match.groups()
        delta = (WEEKDAYS[weekday] - today.weekday()) % 7
        if modifier == "next":
            delta += 7
        return today + timedelta(days=delta), None
    if re.search(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{month_names})\b|\b(?:{month_names})\s+\d{{1,2}}\b|\b\d{{4}}-\d", text):
        return None, "invalid_date"
    return None, None


def _make_date(year: int, month: int, day: int, infer_year: bool = False,
               today: Optional[date] = None) -> tuple[Optional[date], Optional[str]]:
    try:
        result = date(year, month, day)
        if infer_year and today and result < today:
            result = date(year + 1, month, day)
        return result, None
    except ValueError:
        return None, "invalid_date"


def _extract_name(text: str, patterns: tuple[str, ...]) -> Optional[str]:
    boundaries = {"child", "children", "son", "daughter", "age", "aged", "date", "appointment",
                  "contact", "phone", "number", "tomorrow", "today", *WEEKDAYS}
    for pattern in patterns:
        match = re.search(pattern + r"\s+([a-z][a-z'-]{0,39}(?:\s+[a-z][a-z'-]{0,39})?)", text)
        if match:
            words = match.group(1).split()
            words = words[:next((index for index, word in enumerate(words) if word in boundaries), len(words))]
            if words:
                return " ".join(word.capitalize() for word in words)
    return None


@dataclass
class Parsed:
    text: str
    norm: str
    intent: str = "UNKNOWN"
    date: Optional[date] = None
    date_error: Optional[str] = None
    guardian_name: Optional[str] = None
    child_name: Optional[str] = None
    child_age: Optional[int] = None
    contact: Optional[str] = None
    email: Optional[str] = None
    verification_code: Optional[str] = None
    token: Optional[int] = None
    yes: bool = False
    no: bool = False
    empty: bool = False
    fixes: list[str] = None

    def summary(self) -> dict:
        values = {
            "date": self.date.isoformat() if self.date else None,
            "date_error": self.date_error,
            "guardian_name_provided": bool(self.guardian_name),
            "child_name_provided": bool(self.child_name),
            "child_age_provided": self.child_age is not None,
            "contact_provided": bool(self.contact),
            "email_provided": bool(self.email),
            "verification_code_provided": bool(self.verification_code),
            "token": self.token,
            "yes": self.yes,
            "no": self.no,
        }
        return {key: value for key, value in values.items() if value is not None and value is not False}


def parse(text: str, today: date) -> Parsed:
    norm = normalize(text)
    normalized_numbers = numberize(norm)
    parsed = Parsed(text=text or "", norm=norm, fixes=[])
    parsed.empty = not normalized_numbers
    if parsed.empty:
        parsed.intent = "EMPTY"
        return parsed

    parsed.date, parsed.date_error = extract_date(normalized_numbers, today)
    email_match = re.search(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", norm)
    if email_match:
        parsed.email = email_match.group(0).casefold()
    code_match = re.search(r"\b(?:verification )?code\s+(\d{6})\b|\b(\d{6})\b", normalized_numbers)
    if code_match:
        parsed.verification_code = code_match.group(1) or code_match.group(2)
    parsed.guardian_name = _extract_name(normalized_numbers, (
        r"(?:parent|guardian)(?:'s)? name(?: is)?",
        r"(?:my name is|i am|i'm|this is|call me|parent is|guardian is)",
    ))
    parsed.child_name = _extract_name(normalized_numbers, (
        r"(?:child|children|son|daughter)(?:'s)? name(?: is)?",
        r"(?:my child|my son|my daughter) is called",
        r"(?:child|son|daughter) is",
    ))
    age_match = re.search(r"\b(?:age|aged|is)\s+(\d{1,3})(?:\s*(?:years?|months?)\s*(?:old)?)?\b|\b(\d{1,3})\s*(?:years?|months?)\s*old\b", normalized_numbers)
    if age_match:
        parsed.child_age = int(age_match.group(1) or age_match.group(2))
    token_match = re.search(r"\btoken(?: number)?\s+(\d{1,2})\b|\bnumber\s+(\d{1,2})\b", normalized_numbers)
    if token_match:
        parsed.token = int(token_match.group(1) or token_match.group(2))
    contact_text = re.sub(r"\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", " ", norm)
    contact_match = re.search(r"(?<!\w)(\+?\d[\d ()-]{5,}\d)(?!\w)", contact_text)
    if contact_match:
        digits = re.sub(r"\D", "", contact_match.group(1))
        if 7 <= len(digits) <= 15:
            parsed.contact = "+" + digits if contact_match.group(1).strip().startswith("+") else digits

    cleaned = re.sub(r"\b(no problem|no worries|not a problem)\b", " ", normalized_numbers)
    parsed.yes = bool(re.search(r"\b(yes|yeah|yep|sure|correct|okay|ok|confirm|confirmed|absolutely)\b|\b(go ahead|please do|that works)\b", cleaned))
    parsed.no = bool(re.search(r"\b(no|nope|nah|cancel that|do not|don't)\b", cleaned))
    if re.search(r"\b(reschedule|rescheduling|move my appointment|change my appointment)\b", norm):
        parsed.intent = "RESCHEDULE"
    elif re.search(r"\b(cancel|cancellation|cancel my appointment)\b", norm):
        parsed.intent = "CANCEL"
    elif re.search(r"\b(check|find|look up|status|when is|what time is)\b", norm) and re.search(r"\b(appointment|token)\b", norm):
        parsed.intent = "CHECK"
    elif re.search(r"\b(book|booking|appointment|schedule|see the doctor)\b", norm):
        parsed.intent = "BOOK"
    elif re.search(r"\b(hello|hi|hey|good morning|good afternoon)\b", norm):
        parsed.intent = "GREETING"
    elif re.search(r"\b(help|what can you do)\b", norm):
        parsed.intent = "HELP"
    elif re.search(r"\b(bye|goodbye|hang up)\b", norm):
        parsed.intent = "GOODBYE"
    return parsed
