"""Small, auditable English grammar. Unsupported or ambiguous text is clarified.

There is intentionally no general-purpose NLU, probabilistic score, or LLM.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.schemas import Entities, Intent


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("a.m.", "am").replace("p.m.", "pm")
    return re.sub(r"\s+", " ", text).strip(" .!?\t\n")


@dataclass
class Recognition:
    intent: Intent
    rule: str


def recognize(text: str, active: bool = False) -> Recognition:
    t = normalize(text)
    # Discourse markers do not change the request: "All right, make a booking".
    t = re.sub(r"^(?:(?:all right|alright|well|so|uh|um)[,\s]+)+", "", t)
    rules = [
        (Intent.END, "control.end", r"(?:goodbye|bye|end (?:the )?(?:call|conversation)|stop|hang up)"),
        (Intent.REPEAT, "control.repeat", r"(?:repeat(?: that)?|say that again|pardon|what did you say)"),
        (Intent.DENY, "confirmation.deny", r"(?:no(?: thanks| thank you)?|nope|not yet|do not|don't|do not (?:book|cancel)|don't (?:book|cancel)|never mind|nevermind|forget it)"),
        (Intent.CONFIRM, "confirmation.explicit", r"(?:(?:yes|yeah|yep|sure|okay|ok)(?: please)?|sounds good|confirm(?: it| booking| cancellation| reschedule)?|go ahead|that's correct|that is correct|correct|please confirm)"),
    ]
    for intent, rule, pattern in rules:
        if re.fullmatch(pattern, t):
            return Recognition(intent, rule)
    if re.search(r"\b(?:do not|don't|never)\s+(?:want (?:you )?to\s+)?(?:cancel|book|reschedule|make (?:a|an) (?:booking|appointment))\b|\b(?:do not|don't) want (?:a|an) (?:haircut|beard trim|appointment)\b", t):
        return Recognition(Intent.DENY, "action.negated")
    if re.search(r"\breference\b", t) and re.search(r"\b(?:where|find|what|don't know|do not know|cannot see|can't see|don't have)\b", t):
        return Recognition(Intent.INFO, "booking.reference_help")
    if re.search(r"\b(?:have you (?:booked|scheduled|reserved|cancelled|canceled|rescheduled)|did you (?:book|schedule|reserve|cancel|reschedule)|is (?:my|the|that) (?:booking|appointment) (?:confirmed|booked|cancelled|canceled)|booking status)\b", t):
        return Recognition(Intent.INFO, "booking.status_question")
    if re.search(r"\b(?:hours|prices?|cost|how much|services|address|where are you|when do you open|what time do you (?:open|close)|what do you offer)\b", t) or re.search(r"\bhow (?:(?:do|can) i |to )(?:cancel|book|reschedule|make (?:a|an) (?:booking|appointment))\b", t):
        return Recognition(Intent.INFO, "business.question")
    actions = []
    if re.search(r"\b(?:cancel|remove|delete)\s+(?:(?:my|the|an|this|a)\s+)?(?:appointment|booking|reservation|it|that|nl[- ]?[a-z0-9]{8})\b|^cancel$", t):
        actions.append(Intent.CANCEL)
    if re.search(r"\b(?:reschedule|move)\b|\bchange\s+(?:my|the|an)\s+(?:appointment|booking)\b", t):
        actions.append(Intent.RESCHEDULE)
    if re.search(r"\b(?:availability|available|openings?|free slots?)\b", t):
        actions.append(Intent.AVAILABILITY)
    booking_command = r"^(?:(?:yes|yeah|yep|okay|ok|sure|please)[,\s]+)*(?:book|schedule|reserve)\b"
    booking_request = r"\b(?:to|can you|could you|please|let's|and) (?:book|schedule|reserve)\b|\b(?:make|arrange)\s+(?:a|an|my|the)\s+(?:booking|appointment|reservation)\b"
    service_request = r"\b(?:want|need|like|can i|could i)\s+(?:you to\s+|to\s+)?(?:(?:make|book|get|have|schedule|reserve)\s+)?(?:a|an)\s+(?:haircut|hair cut|beard trim|appointment)\b"
    if re.search(booking_command, t) or re.search(booking_request, t) or re.search(service_request, t):
        actions.append(Intent.CREATE)
    if len(set(actions)) > 1:
        return Recognition(Intent.UNKNOWN, "action.multiple_requests")
    if actions:
        return Recognition(actions[0], "action." + actions[0].name.lower())
    if t in ("i said", "no i said") or re.search(r"\b(?:actually|instead|meant|make it|change that|change (?:the )?(?:time|date|service|name)|start over|restart)\b", t):
        return Recognition(Intent.MODIFY, "context.correction")
    return Recognition(Intent.UNKNOWN, "context.details" if active else "fallback.unknown")


@dataclass
class Extraction:
    entities: Entities = field(default_factory=Entities)
    issues: dict[str, str] = field(default_factory=dict)


WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
           "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
NUMBER_PATTERN = "(?:" + "|".join(NUMBERS) + r"|\d{1,2})"


def extract(text: str, now: datetime, *, expecting_name: bool = False, expecting_time: bool = False) -> Extraction:
    result = Extraction()
    e, issues = result.entities, result.issues
    t = normalize(text)
    ref = re.search(r"\bnl[- ]?([a-z0-9]{8})\b", t)
    if ref:
        e.reference = "NL-" + ref[1].upper()
    # References contain arbitrary letters/digits; never parse them as names/times.
    clean = re.sub(r"\bnl[- ]?[a-z0-9]{8}\b", "", t)
    # In an explicit directional change, the source is not a second requested
    # value. Alternatives without a direction still trigger ambiguity below.
    if re.search(r"\b(?:change|move|reschedule|switch)\b", clean):
        clean = re.sub(r"\bfrom\s+.+?\s+to\s+", "to ", clean, count=1)
    haircut = bool(re.search(r"\b(?:haircut|hair cut|classic cut|trim my hair)\b", clean))
    beard = bool(re.search(r"\b(?:beard|beard trim)\b", clean))
    if re.search(r"\b(?:combo|both)\b", clean) or (haircut and beard):
        e.service = "combo"
    elif haircut:
        e.service = "haircut"
    elif beard:
        e.service = "beard"
    if haircut and beard and re.search(r"\b(?:or|not|instead of|rather than)\b", clean):
        e.service = None
        issues["service"] = "Which one service should I use: haircut, beard trim, or the combination?"
    if re.search(r"\b(?:color|colour|massage|nails|facial|dye|perm)\b", clean):
        e.service = None
        issues["service"] = "We offer haircuts, beard trims, or the combination. Which would you like?"

    dates: set[str] = set()
    iso_matches = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", clean)
    for value in iso_matches:
        try:
            dates.add(datetime.strptime(value, "%Y-%m-%d").date().isoformat())
        except ValueError:
            issues["date"] = "That date does not exist. Please use a weekday or YYYY-MM-DD."
    date_clean = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", clean)
    if re.search(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b", date_clean):
        issues["date"] = "Numeric dates can mean different things. Please use YYYY-MM-DD or a weekday."
    relative = date_clean
    if "day after tomorrow" in relative:
        dates.add((now.date() + timedelta(days=2)).isoformat())
        relative = relative.replace("day after tomorrow", "")
    if re.search(r"\btomorrow\b", relative):
        dates.add((now.date() + timedelta(days=1)).isoformat())
    if re.search(r"\btoday\b", relative):
        dates.add(now.date().isoformat())
    if re.search(r"\byesterday\b", relative):
        dates.add((now.date() - timedelta(days=1)).isoformat())
    for index, day in enumerate(WEEKDAYS):
        if re.search(rf"\b{day}\b", relative):
            offset = (index - now.weekday()) % 7
            if re.search(rf"\bnext {day}\b", relative) and offset == 0:
                offset = 7
            dates.add((now.date() + timedelta(days=offset)).isoformat())
    if len(dates) > 1:
        issues["date"] = "I heard more than one date. Please give one date for this appointment."
    elif dates:
        e.date = next(iter(dates))
    if re.search(r"\b(?:next week|next month|weekend|sometime|later)\b", clean) and not dates:
        issues["date"] = "Which exact day? You can say tomorrow, next Monday, or YYYY-MM-DD."

    periods = set(re.findall(r"\b(morning|afternoon|evening)\b", clean))
    if len(periods) > 1:
        issues["time"] = "I heard multiple parts of the day. Please give one time with AM or PM."
    elif periods:
        e.period = next(iter(periods))
    # Convert spoken times before running one numeric grammar.
    time_text = re.sub(r"\bhalf past (" + NUMBER_PATTERN + r")\b", lambda m: f"{NUMBERS.get(m[1], m[1])}:30", date_clean)
    time_text = re.sub(r"\bquarter past (" + NUMBER_PATTERN + r")\b", lambda m: f"{NUMBERS.get(m[1], m[1])}:15", time_text)
    time_text = re.sub(r"\b(" + "|".join(NUMBERS) + r") (thirty|fifteen|forty five)\b",
                       lambda m: f"{NUMBERS[m[1]]}:{ {'thirty': '30', 'fifteen': '15', 'forty five': '45'}[m[2]]}", time_text)
    for word, number in NUMBERS.items():
        time_text = re.sub(rf"\b{word}\b", str(number), time_text)
    time_text = time_text.replace("o'clock", "")
    candidates: set[tuple[int, int, str]] = set()
    for match in re.finditer(r"(?<![\w/-])(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?![\w/-])", time_text):
        prefix = time_text[:match.start()]
        has_context = bool(match[2] or match[3] or re.search(r"\b(?:at|to|make it|for)\s*$", prefix) or expecting_time or re.fullmatch(r"\s*\d{1,2}\s*(?:instead)?\s*", time_text))
        if has_context:
            candidates.add((int(match[1]), int(match[2] or 0), match[3] or ""))
    times = set()
    for hour, minute, suffix in candidates:
        if minute > 59 or hour > 23 or (suffix and not 1 <= hour <= 12):
            issues["time"] = "That time is invalid. Please use a time like 5:30 PM or 17:30."
            continue
        if suffix:
            hour = hour % 12 + (12 if suffix == "pm" else 0)
        elif e.period:
            if not 1 <= hour <= 12:
                issues["time"] = "Please give one time with AM or PM."
                continue
            hour = hour % 12 + (0 if e.period == "morning" else 12)
        elif hour < 13 and hour != 0:
            issues["time"] = "Is that AM or PM? Please say the full time, for example 5 PM."
            continue
        times.add(f"{hour:02d}:{minute:02d}")
    if re.search(r"\bnoon\b", clean):
        times.add("12:00")
    if re.search(r"\bmidnight\b", clean):
        times.add("00:00")
    if len(times) > 1:
        issues["time"] = "I heard more than one time. Please give one time with AM or PM."
    elif times:
        e.time = next(iter(times))
        e.period = None
    if re.search(r"\b(?:at|to)\s+\d{1,2}:\d{1}(?!\d)", time_text):
        issues["time"] = "Please give the complete time, for example 5:30 PM."

    name_match = re.search(r"\b(?:my name is|name is|name's|i am|i'm|under the name|call me)\s+([a-z][a-z '\-]{0,79})", t)
    candidate = name_match[1] if name_match else (text.strip() if expecting_name else "")
    # Full-string names only; corrections, requests and entities cannot become names.
    if candidate and not (dates or candidates or e.service or e.reference or issues):
        candidate = re.sub(r"[.!?]+$", "", candidate).strip()
        if expecting_name:
            candidate = re.sub(r"^(?:(?:and|uh|um|erm|well|okay|ok|it's|it is)[,\s]+)+", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"[,\s]+(?:please|thanks|thank you)$", "", candidate, flags=re.IGNORECASE)
        reserved = r"\b(?:and|or|yes|yeah|sure|no|actually|tomorrow|today|book|cancel|reschedule|instead|meant|please|unknown|hello|hi|thanks|restart|repeat|stop|help|want|need|weather|pizza|what|why|how|when|where|change|make|confirm|afternoon|evening|morning|don't|not|know|maybe|whatever|anything|tell|show|order|sing|play|can|could|would|is|are|does)\b"
        if re.fullmatch(r"[^\W\d_]+(?:[ '\-][^\W\d_]+){0,3}", candidate, re.UNICODE) and not re.search(reserved, normalize(candidate)) and 2 <= len(candidate) <= 80:
            e.name = candidate.title()
    for key in issues:
        setattr(e, key, None)
    return result
