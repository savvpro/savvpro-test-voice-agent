"""Small, auditable English grammar. Unsupported or ambiguous text is clarified.

There is intentionally no general-purpose NLU, probabilistic score, or LLM.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime

from app.brain.calendar_dates import extract_dates
from app.schemas import Entities, Intent


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("a.m.", "am").replace("p.m.", "pm")
    return re.sub(r"\s+", " ", text).strip(" .!?\t\n")


def intent_text(text: str) -> str:
    """Remove bounded spoken repair prefixes without stripping negation."""
    t = re.sub(r"[,;]+", " ", normalize(text))
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"^(?:(?:all right|alright|well|so|uh|um|i said|i (?:already )?told you(?: that)?)[,\s]+)+", "", t)


AFFIRMATIVE = r"(?:yes|yeah|yep|sure|okay|ok)"
BOOKING_OBJECT = r"(?:(?:a|an|my|the)\s+)?(?:(?:new|another)\s+)?(?:booking|appointment|reservation)"


def confirms_action(text: str, intent: Intent) -> bool:
    """A bounded affirmative action phrase may confirm an existing proposal."""
    verbs = {Intent.CREATE: r"(?:book|reserve|schedule)",
             Intent.RESCHEDULE: r"(?:reschedule|move)", Intent.CANCEL: "cancel"}
    verb = verbs.get(intent)
    if not verb:
        return False
    target = r"(?:it|(?:this|that)(?: (?:slot|appointment|booking))?)"
    return bool(re.fullmatch(rf"{AFFIRMATIVE}(?: please)? {verb} {target}(?: please)?", intent_text(text)))


@dataclass
class Recognition:
    intent: Intent
    rule: str


def recognize(text: str, active: bool = False) -> Recognition:
    t = intent_text(text)
    rules = [
        (Intent.END, "control.end", r"(?:goodbye|bye|end (?:the )?(?:call|conversation)|stop|hang up)"),
        (Intent.REPEAT, "control.repeat", r"(?:repeat(?: that)?|say that again|pardon|what did you say)"),
        (Intent.DENY, "confirmation.deny", r"(?:no(?: thanks| thank you)?|nope|not yet|do not|don't|do not (?:book|cancel)|don't (?:book|cancel)|never mind|nevermind|forget it)"),
        (Intent.CONFIRM, "confirmation.explicit", rf"(?:{AFFIRMATIVE}(?: please)?(?: (?:do it|go ahead))?|sounds good|confirm(?: it| booking| cancellation| reschedule)?|(?:please )?do it|go ahead|that's correct|that is correct|correct|please confirm)"),
    ]
    for intent, rule, pattern in rules:
        if re.fullmatch(pattern, t):
            return Recognition(intent, rule)
    if re.search(rf"\b(?:do not|don't|never)\s+(?:want (?:you )?to\s+)?(?:cancel|book|reschedule|(?:make|arrange)\s+{BOOKING_OBJECT})\b|\b(?:do not|don't) want (?:a|an) (?:haircut|beard trim|appointment)\b", t):
        return Recognition(Intent.DENY, "action.negated")
    if re.search(r"\breference\b", t) and re.search(r"\b(?:where|find|what|don't know|do not know|cannot see|can't see|don't have)\b", t):
        return Recognition(Intent.INFO, "booking.reference_help")
    if re.search(r"\b(?:have you (?:booked|scheduled|reserved|cancelled|canceled|rescheduled)|did you (?:book|schedule|reserve|cancel|reschedule)|is (?:my|the|that) (?:booking|appointment) (?:confirmed|booked|cancelled|canceled)|booking status)\b", t):
        return Recognition(Intent.INFO, "booking.status_question")
    if re.search(r"\b(?:hours|prices?|cost|how much|services|address|where are you|when do you open|what time do you (?:open|close)|what do you offer)\b", t) or re.search(rf"\bhow (?:(?:do|can) i |to )(?:cancel|book|reschedule|(?:make|arrange)\s+{BOOKING_OBJECT})\b", t):
        return Recognition(Intent.INFO, "business.question")
    actions = []
    if re.search(r"\b(?:cancel|remove|delete)\s+(?:(?:my|the|an|this|a)\s+)?(?:appointment|booking|reservation|it|that|nl[- ]?[a-z0-9]{8})\b|^cancel$", t):
        actions.append(Intent.CANCEL)
    if re.search(r"\b(?:reschedule|move)\b|\bchange\s+(?:my|the|an)\s+(?:appointment|booking)\b", t):
        actions.append(Intent.RESCHEDULE)
    if re.search(r"\b(?:availability|available|openings?|free slots?)\b", t):
        actions.append(Intent.AVAILABILITY)
    booking_command = r"^(?:(?:yes|yeah|yep|okay|ok|sure|please)[,\s]+)*(?:book|schedule|reserve)\b"
    booking_request = rf"\b(?:to|can you|could you|please|let's|and) (?:book|schedule|reserve)\b|\b(?:make|arrange)\s+{BOOKING_OBJECT}\b"
    service_request = r"\b(?:want|need|like|can i|could i)\s+(?:you to\s+|to\s+)?(?:(?:make|book|get|have|schedule|reserve)\s+)?(?:a|an)\s+(?:haircut|hair cut|beard trim|appointment)\b"
    if re.search(booking_command, t) or re.search(booking_request, t) or re.search(service_request, t):
        actions.append(Intent.CREATE)
    if len(set(actions)) > 1:
        return Recognition(Intent.UNKNOWN, "action.multiple_requests")
    if actions:
        return Recognition(actions[0], "action." + actions[0].name.lower())
    if re.match(rf"^{AFFIRMATIVE}\s+(?:please\s+)?(?:(?:do it|go ahead)\b|(?:at|around|about|on|for|today|tomorrow)\b)", t):
        # An affirmative with details can revise a proposal, never directly
        # confirm it. The engine applies the details and requests fresh review.
        return Recognition(Intent.MODIFY, "confirmation.with_details")
    if t in ("i said", "no i said") or re.search(r"\b(?:actually|instead|meant|make it|change that|change (?:the )?(?:time|date|service|name)|start over|restart)\b", t):
        return Recognition(Intent.MODIFY, "context.correction")
    return Recognition(Intent.UNKNOWN, "context.details" if active else "fallback.unknown")


@dataclass
class Extraction:
    entities: Entities = field(default_factory=Entities)
    issues: dict[str, str] = field(default_factory=dict)


NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
           "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
NUMBER_PATTERN = "(?:" + "|".join(NUMBERS) + r"|\d{1,2})"


def customer_name(text: str, *, expecting_name: bool) -> str | None:
    """Extract an entire name slot using bounded, anchored request wrappers."""
    candidate = intent_text(text)
    candidate = re.sub(r"^(?:(?:actually|please)[,\s]+)+", "", candidate)
    candidate = re.sub(r"^(?:could you|can you|would you|i want you to)\s+(?:please\s+)?", "", candidate)
    explicit = re.fullmatch(
        r"(?:use (?:(?:the|my) )?name(?: (?:is|of))?"
        r"|put (?:it|(?:(?:the|my) )?(?:booking|appointment)) under(?: the name)?"
        r"|under(?: the name)?|(?:my|the) name is|name is|name's|i am|i'm|call me)\s+(.+)",
        candidate,
    )
    if explicit:
        candidate = explicit[1]
    elif expecting_name:
        candidate = re.sub(r"^(?:(?:and|uh|um|erm|well|okay|ok|it's|it is)[,\s]+)+", "", candidate)
        candidate = re.sub(r"^use\s+", "", candidate)
    else:
        return None
    candidate = re.sub(r"[,\s]+(?:please|thanks|thank you)$", "", candidate).strip()
    # Reject instruction fragments and alternatives rather than storing them.
    reserved = r"\b(?:and|or|yes|yeah|yep|sure|okay|ok|no|actually|tomorrow|today|book|booking|appointment|cancel|reschedule|instead|meant|please|unknown|hello|hi|thanks|restart|repeat|stop|help|want|need|weather|pizza|what|why|how|when|where|change|make|confirm|correct|afternoon|evening|morning|don't|not|know|maybe|whatever|anything|tell|show|order|sing|play|can|could|would|is|are|does|use|name|put|under|previous|another|discount)\b"
    if (2 <= len(candidate) <= 80
            and re.fullmatch(r"[^\W\d_]+(?:[ '\-][^\W\d_]+){0,3}", candidate, re.UNICODE)
            and not re.search(reserved, candidate)):
        return candidate.title()
    return None


def extract(text: str, now: datetime, *, expecting_name: bool = False, expecting_time: bool = False, expecting_date: bool = False) -> Extraction:
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

    calendar = extract_dates(clean, now, expecting_date=expecting_date)
    dates, date_clean = calendar.values, calendar.remainder
    if calendar.issue:
        issues["date"] = calendar.issue
    if len(dates) == 1:
        e.date = next(iter(dates))

    periods = set(re.findall(r"\b(morning|afternoon|evening)\b", clean))
    if len(periods) > 1:
        issues["time"] = "I heard multiple parts of the day. Please give one time with AM or PM."
    elif periods:
        e.period = next(iter(periods))
    # Convert spoken times before running one numeric grammar.
    time_text = re.sub(r"\bhalf past (" + NUMBER_PATTERN + r")\b", lambda m: f"{NUMBERS.get(m[1], m[1])}:30", date_clean)
    time_text = re.sub(r"\bquarter past (" + NUMBER_PATTERN + r")\b", lambda m: f"{NUMBERS.get(m[1], m[1])}:15", time_text)
    time_text = re.sub(r"\b(" + NUMBER_PATTERN + r") (thirty|fifteen|forty five)\b",
                       lambda m: f"{NUMBERS.get(m[1], m[1])}:{ {'thirty': '30', 'fifteen': '15', 'forty five': '45'}[m[2]]}", time_text)
    for word, number in NUMBERS.items():
        time_text = re.sub(rf"\b{word}\b", str(number), time_text)
    time_text = time_text.replace("o'clock", "")
    # Speech recognition commonly omits a colon: "five 30 PM" -> "5:30 PM".
    # Never join alternatives such as "4 or 5 PM" or guess a missing digit.
    time_text = re.sub(r"(?<![\w:/-])(\d{1,2})\s+(\d{2})(?![\w:/-])", r"\1:\2", time_text)
    candidates: set[tuple[int, int, str]] = set()
    for match in re.finditer(r"(?<![\w/-])(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?![\w/-])", time_text):
        prefix = time_text[:match.start()]
        has_context = bool(match[2] or match[3] or re.search(r"\b(?:at|to|make it|for|around|about|approximately|roughly)\s*$", prefix) or expecting_time or re.fullmatch(r"\s*\d{1,2}\s*(?:instead)?\s*", time_text))
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
    if not e.time and "time" not in issues and re.search(r"\b(?:at|around|about|approximately|roughly)\s+(?:\d|thirteen\b|fourteen\b|fifteen\b|sixteen\b|seventeen\b|eighteen\b|nineteen\b|twenty\b|thirty\b|forty\b|fifty\b)", time_text):
        issues["time"] = "I couldn't interpret that time. Please say the full time, such as 4:30 PM."
    if re.search(r"\b(?:at|to)\s+\d{1,2}:\d{1}(?!\d)", time_text):
        issues["time"] = "Please give the complete time, for example 5:30 PM."

    # Other slot values and corrections cannot accidentally become names.
    if not (dates or candidates or e.service or e.reference or issues):
        e.name = customer_name(text, expecting_name=expecting_name)
    for key in issues:
        setattr(e, key, None)
    return result
