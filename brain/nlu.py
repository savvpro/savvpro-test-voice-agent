import re
from datetime import datetime
from typing import Any, Dict

import dateparser
from dateparser.search import search_dates


_INTENTS = ("book", "change", "cancel", "confirm_yes", "confirm_no",
            "out_of_scope", "unclear")
_DAYS = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
_TIME_RE = re.compile(
    r"\b(?:at\s+)?(\d{1,2})(?:(:|\.)(\d{2}))?\s*(am|pm)\b", re.I
)
_DATE_RE = re.compile(
    rf"\b(?:today|tomorrow|tonight|next\s+week|{_DAYS})\b|\b\d{{4}}-\d{{2}}-\d{{2}}\b",
    re.I,
)
_FILLER_WORDS = {
    "a", "am", "dont", "fine", "i", "idk", "im", "know", "no", "not",
    "the", "uh", "um", "whatever", "well", "works", "yeah",
}
_LEADING_FILLERS_RE = re.compile(r"^(?:(?:yeah|yes|um|uh|well)\s+|it['’]?s\s+)+", re.I)
_CONFIRM_YES_RE = re.compile(
    r"\b(?:yes|y|yeah|yep|yup|ok|okay|sure|correct|right|confirm)\b"
    r"|\b(?:sounds\s+good|go\s+ahead|that['’]?s\s+right|book\s+it)\b",
    re.I,
)
_CONFIRM_NO_RE = re.compile(
    r"\b(?:no|n|nope|nah|wrong|incorrect)\b"
    r"|\b(?:not\s+really|not\s+quite|change\s+it)\b",
    re.I,
)


def _date_value(text: str) -> str | None:
    matches = search_dates(
        text,
        settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": datetime.now()},
    )
    if not matches:
        return None
    for phrase, parsed in matches:
        if _DATE_RE.search(phrase):
            return parsed.date().isoformat()
    return None


def _time_value(text: str, pending_slot: str | None = None) -> str | None:
    normalized = re.sub(r"\b([ap])\s*\.\s*m\.?\b", r"\1m", text, flags=re.I)
    match = _TIME_RE.search(normalized)
    if not match:
        match_24h = re.search(r"\b(?:at\s+)?([01]?\d|2[0-3]):([0-5]\d)\b", normalized, re.I)
        if match_24h:
            return f"{int(match_24h.group(1)):02d}:{match_24h.group(2)}"
        if pending_slot == "time":
            bare_24h = re.search(
                r"\b(1[3-9]|2[0-3]|[01]\d[0-5]\d|2[0-3][0-5]\d)\b", normalized
            )
            if bare_24h:
                digits = bare_24h.group(1)
                if len(digits) <= 2:
                    return f"{int(digits):02d}:00"
                return f"{int(digits[:2]):02d}:{digits[2:]}"
        return None
    hour = int(match.group(1))
    minute = int(match.group(3) or 0)
    meridiem = match.group(4).lower()
    if hour > 12 or minute > 59:
        return None
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def parse_text(
    text: str, current_state: str = "GREETING", pending_slot: str | None = None
) -> Dict[str, Any]:
    text = text.strip()
    lowered = text.lower()
    result: Dict[str, Any] = {"intent": "unclear", "slots": {}}
    if not text:
        return result

    if re.search(r"\b(cancel|stop|never mind|nevermind)\b", lowered):
        result["intent"] = "cancel"
        return result
    if current_state == "CONFIRMING":
        if _CONFIRM_YES_RE.search(lowered):
            result["intent"] = "confirm_yes"
            return result
        if _CONFIRM_NO_RE.search(lowered):
            result["intent"] = "confirm_no"
            return result
    if re.search(r"\b(do you do|provide|offer).*\b(dental|legal|hair|restaurant)\b", lowered):
        result["intent"] = "out_of_scope"
        return result
    normalized_words = re.sub(r"[^\w'’]+", " ", lowered.replace("’", "'")).strip()
    if normalized_words and all(word in _FILLER_WORDS for word in normalized_words.split()):
        result["filler_only"] = True
        return result

    if re.search(r"\b(hello|hi|hey|book|appointment|schedule|doctor|clinic|see a doctor)\b", lowered):
        result["intent"] = "book"
    elif re.search(r"\b(change|instead|actually|different)\b", lowered):
        result["intent"] = "change"

    slots = result["slots"]
    negated_date = re.search(r"\b(?:no|not)\b.*\b(" + _DAYS + r")\b", lowered)
    if negated_date:
        slots["date"] = None
    else:
        date = _date_value(text)
        if date:
            slots["date"] = date

    time = _time_value(text, pending_slot)
    if time:
        slots["time"] = time
    result["ambiguous_time"] = (
        not time
        and bool(re.search(r"\b(?:at|around|about)?\s*(?:[1-9]|1[0-2])\b", lowered))
    )

    reason_match = re.search(r"\bfor\s+(?:a\s+|an\s+)?([a-z][a-z -]{2,30}?)(?:\s+on\b|\s+at\b|$)", lowered)
    if reason_match:
        slots["reason"] = reason_match.group(1).strip()
    else:
        reason_match = re.search(
            r"\b(?:a|an)\s+(checkup|physical|consultation|vaccination|follow[- ]up)\b",
            lowered,
        )
        if reason_match:
            slots["reason"] = reason_match.group(1).strip()
    if pending_slot == "reason" and "reason" not in slots:
        reason = _LEADING_FILLERS_RE.sub("", text).strip()
        if reason and not reason.isdigit():
            slots["reason"] = reason

    name_match = re.search(r"\b(?:my name is|name is|i am)\s+([A-Za-z][A-Za-z '-]+)", text, re.I)
    if name_match:
        slots["patient_name"] = name_match.group(1).strip()
    phone_match = re.search(r"(?<!\d)(?:\+?1[\s.-]?)?(\d[\d\s().-]{8,}\d)(?!\d)", text)
    if phone_match and (
        pending_slot == "phone"
        or not re.fullmatch(r"(?:\+?[\d\s().-]){7,}", text)
    ):
        digits = re.sub(r"\D", "", phone_match.group(0))
        if len(digits) >= 10:
            slots["phone"] = digits[-10:]

    if current_state == "COLLECTING":
        if (
            pending_slot == "patient_name"
            and "patient_name" not in slots
            and not any(slot in slots for slot in ("date", "time", "reason"))
            and not re.search(r"\b(actually|change|make it|instead)\b", lowered)
            and re.fullmatch(r"[A-Za-z][A-Za-z '-]{1,40}", text)
        ):
            slots["patient_name"] = text.strip()
        if pending_slot == "phone" and "phone" not in slots and re.fullmatch(
            r"(?:\+?[\d\s().-]){7,}", text
        ):
            digits = re.sub(r"\D", "", text)
            if len(digits) >= 10:
                slots["phone"] = digits[-10:]
    return result
