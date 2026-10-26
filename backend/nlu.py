"""Deterministic English grammar. No model, embedding, or remote decision service."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


@dataclass
class Parsed:
    intent: str | None = None
    slots: dict[str, str] = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    issue: str | None = None
    yes: bool = False
    no: bool = False
    selection: int | None = None
    reference: str | None = None


WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
}
WEEKDAYS = "monday tuesday wednesday thursday friday saturday sunday".split()
MONTHS = (
    "january february march april may june july august september october november december".split()
)


def parse(text: str, now: datetime, awaiting_time: bool = False) -> Parsed:
    p = Parsed()
    raw = text.lower().replace("’", "'").strip()
    normalized = re.sub(r"\b([ap])\.?\s*m\.?\b", r"\1m", raw)
    clean = re.sub(r"\b(?:don't|do not|never)\s+cancel\b", "", normalized)
    if clean != normalized:
        p.rules.append("negated_cancel_excluded")
    if re.search(r"\b(reschedule|rebook|move|change.*(?:appointment|booking)|push.*back)\b", clean):
        p.intent = "RESCHEDULE"
    elif re.search(r"\b(cancel|cancellation|delete.*booking)\b", clean):
        p.intent = "CANCEL"
    elif re.search(
        r"\b(book|reserve|schedule|arrange)\b|\b(?:need|want|like) (?:an? )?appointment\b", clean
    ):
        p.intent = "BOOK"
    if re.search(r"\b(?:when|what time).*(?:close|open)|\b(?:hours|opening|closing)\b", raw):
        p.intent = "HOURS"
    elif re.search(
        r"\b(?:what|which).*(?:services|offer)|\bhow long\b|\b(?:cost|price|prices)\b", raw
    ):
        p.intent = "SERVICES"
    elif re.search(r"\b(?:list|show|what are|do i have).*(?:appointments|bookings)\b", raw):
        p.intent = "LIST"
    elif re.search(r"\b(?:repeat|say that again)\b", raw):
        p.intent = "REPEAT"
    elif re.fullmatch(r"(?:thanks?[, ]*)?(?:bye|goodbye|end call|hang up|stop)[.! ]*", raw):
        p.intent = "END"
    elif re.fullmatch(r"(?:help|what can you do)[?! .]*", raw):
        p.intent = "HELP"
    if p.intent:
        p.rules.append("intent_" + p.intent.lower())
    p.yes = bool(
        re.match(
            r"^(?:yes|yeah|yep|confirm|correct|go ahead|sounds good|that's right|please do|book it)\b",
            raw,
        )
    )
    p.no = bool(
        re.fullmatch(r"(?:no|nope|no thanks|not now|nevermind|never mind|forget it)[.! ]*", raw)
    )
    selection = re.search(r"\b(first|second|third|fourth|last)\b", raw)
    if selection:
        p.selection = {"first": 0, "second": 1, "third": 2, "fourth": 3, "last": -1}[selection[1]]
    elif re.fullmatch(r"(?:number |option |appointment )?[1-9]", raw.rstrip(".!? ")):
        p.selection = int(raw.rstrip(".!? ")[-1]) - 1
    else:
        spoken_choice = re.fullmatch(
            r"(?:number |option |appointment )?(one|two|three|four|five|six|seven|eight|nine)",
            raw.rstrip(".!? "),
        )
        if spoken_choice:
            p.selection = int(WORDS[spoken_choice[1]]) - 1
    reference = re.search(r"\b[a-f0-9]{8}\b", raw)
    if reference:
        p.reference = reference[0].upper()

    aliases = {
        "oil_change": r"\boil(?:\s+(?:change|service))?\b|\blube\b",
        "tyre_rotation": r"\b(?:tyre|tire)(?:s)?(?:\s+(?:rotation|rotate|service))?\b|\bwheel rotation\b",
        "brake_inspection": r"\bbrake(?:s)?(?:\s+(?:inspection|check|service))?\b|\bbreak inspection\b",
    }
    found = [
        (match.start(), key)
        for key, pattern in aliases.items()
        for match in re.finditer(pattern, raw)
    ]
    if found:
        p.slots["service"] = sorted(found)[-1][1]
        p.rules.append("service_alias")
        if len({key for _, key in found}) > 1 and not re.search(
            r"\b(?:actually|instead|not|rather)\b", raw
        ):
            p.issue = "We book one service at a time. Would you like an oil change, tyre rotation, or brake inspection?"
            p.slots.pop("service")
    vehicles = [
        (match.start(), "suv" if match[0] in ("suv", "s.u.v.", "crossover") else "car")
        for match in re.finditer(
            r"\bsuv\b|\bs\.u\.v\.|\bcrossover\b|\bcar\b|\bsedan\b|\bhatchback\b", raw
        )
    ]
    if vehicles:
        p.slots["vehicle"] = sorted(vehicles)[-1][1]
        p.rules.append("vehicle_alias")
    elif re.search(r"\b(?:truck|motorcycle|bike|van)\b", raw):
        p.issue = "This workshop services cars and SUVs. Which of those are you booking?"

    day: date | None = None
    if "day after tomorrow" in raw:
        day = now.date() + timedelta(days=2)
    elif "tomorrow" in raw:
        day = now.date() + timedelta(days=1)
    elif "today" in raw:
        day = now.date()
    elif "yesterday" in raw:
        day = now.date() - timedelta(days=1)
    else:
        weekdays = list(re.finditer(r"\b(?:next |this )?(" + "|".join(WEEKDAYS) + r")\b", raw))
        if weekdays:
            match = weekdays[-1]
            delta = (WEEKDAYS.index(match[1]) - now.weekday()) % 7
            if match[0].startswith("next ") and delta == 0:
                delta = 7
            day = now.date() + timedelta(days=delta)
        iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", raw)
        if iso:
            try:
                day = date(int(iso[1]), int(iso[2]), int(iso[3]))
            except ValueError:
                p.issue = "That calendar date is not valid. Please say the month and day."
        month_pattern = "|".join(MONTHS)
        named = re.search(
            r"\b(" + month_pattern + r")\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b", raw
        )
        reverse = re.search(
            r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + month_pattern + r")(?:\s+(\d{4}))?\b", raw
        )
        if named or reverse:
            calendar_match = named or reverse
            assert calendar_match is not None
            month, number = (
                (MONTHS.index(calendar_match[1]) + 1, int(calendar_match[2]))
                if named
                else (MONTHS.index(calendar_match[2]) + 1, int(calendar_match[1]))
            )
            try:
                day = date(int(calendar_match[3]) if calendar_match[3] else now.year, month, number)
            except ValueError:
                p.issue = "That calendar date is not valid. Please say a valid month and day."
        if re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", raw):
            p.issue = "Please say the month name or use YYYY-MM-DD so the date is unambiguous."
        if re.search(r"\bnext week\b", raw) and day is None:
            p.issue = "Which day next week would you prefer?"
    if day:
        p.slots["date"] = day.isoformat()
        p.rules.append("calendar_date")

    spoken = normalized
    for word, digit in WORDS.items():
        spoken = re.sub(r"\b" + word + r"\b", digit, spoken)
    spoken = re.sub(r"\b(\d{1,2}) thirty\b", r"\1:30", spoken)
    spoken = re.sub(r"\bhalf past (\d{1,2})\b", r"\1:30", spoken)
    spoken = re.sub(r"\bquarter past (\d{1,2})\b", r"\1:15", spoken)
    matches = list(re.finditer(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", spoken))
    if not matches:
        matches = list(re.finditer(r"\bat\s+(\d{1,2})(?::(\d{2}))?\b", spoken))
    if not matches:
        matches = list(re.finditer(r"\b(\d{1,2}):(\d{2})\b", spoken))
    if not matches and awaiting_time:
        matches = list(re.finditer(r"^(\d{1,2})(?::(\d{2}))?(?: o'clock)?[.! ]*$", spoken))
    at: str | None = None
    if re.search(r"\b(?:noon|midday)\b", raw):
        at = "12:00"
    elif "midnight" in raw:
        at = "00:00"
    elif matches:
        match = matches[-1]
        hour, minute = int(match[1]), int(match[2] or 0)
        meridiem = match[3] if match.lastindex and match.lastindex >= 3 else None
        if minute > 59 or hour > 23 or (meridiem and not 1 <= hour <= 12):
            p.issue = "That time is not valid. Please say a time such as 11 AM or 2:30 PM."
        else:
            if meridiem:
                hour = hour % 12 + (12 if meridiem == "pm" else 0)
            elif 1 <= hour <= 6:
                hour += 12
            elif hour in (7, 8):
                p.issue = "Did you mean AM or PM? Our opening hours are 9 AM to 6 PM."
            at = f"{hour:02d}:{minute:02d}"
    if at:
        p.slots["time"] = at
        p.rules.append("clock_time")
    elif re.search(r"\b(?:morning|afternoon|evening)\b", raw):
        p.issue = "What exact time would you like? We use half-hour appointment slots."
    if "confident" not in raw and (p.yes or p.no):
        p.rules.append("confirmation_yes" if p.yes else "confirmation_no")
    return p
