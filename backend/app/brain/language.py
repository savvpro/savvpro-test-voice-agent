"""Small, auditable English grammar. Unsupported or ambiguous text is clarified.

There is intentionally no general-purpose NLU, probabilistic score, or LLM.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime

from app.brain.calendar_dates import extract_dates
from app.brain.clock_times import extract_clock
from app.brain.services import extract_service
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
NAME_PREPOSITION = r"(?:with|for) (?:the )?name"
EXISTING_OBJECT = r"(?:(?:my|the|an|a|this|that|our)\s+)?(?:appointment|booking|reservation)"
SCHEDULE_FIELD = r"(?:time|timing|date|day)"


def schedule_change_field(text: str) -> str | None:
    """A field-only request asks for a value; it cannot reuse a ready proposal."""
    t = intent_text(text)
    time = bool(re.search(r"\b(?:time|timing)\b", t))
    day = bool(re.search(r"\b(?:date|day)\b", t))
    return ("time" if time else "date") if time != day else None


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
        (Intent.DENY, "context.discard_proposal", r"(?:please )?(?:cancel|discard|undo|forget) (?:(?:this|that|the|my) )?(?:change|reschedule|rescheduling|draft|proposal|new booking|new appointment)"),
        (Intent.REPEAT, "control.repeat", r"(?:repeat(?: that)?|say that again|pardon|what did you say)"),
        (Intent.DENY, "confirmation.deny", r"(?:no(?: thanks| thank you)?|nope|not yet|do not|don't|do not (?:book|cancel)|don't (?:book|cancel)|never mind|nevermind|forget it)"),
        (Intent.CONFIRM, "confirmation.explicit", rf"(?:{AFFIRMATIVE}(?: please)?(?: (?:do it|go ahead))?|sounds good|confirm(?: it| booking| cancellation| reschedule)?|(?:please )?do it|go ahead|that's correct|that is correct|correct|please confirm)"),
    ]
    for intent, rule, pattern in rules:
        if re.fullmatch(pattern, t):
            return Recognition(intent, rule)
    if re.search(rf"\b(?:do not|don't|never)\s+(?:want (?:you )?to\s+)?(?:cancel|book|reserve|schedule|reschedule|move|(?:change|adjust|update|shift)\s+(?:(?:my|the|this|that)\s+)?(?:booking|appointment|time|timing|date|day)|(?:make|arrange)\s+{BOOKING_OBJECT})\b|\b(?:do not|don't) want (?:a|an) (?:haircut|beard trim|appointment)\b", t):
        return Recognition(Intent.DENY, "action.negated")
    if re.search(r"\breference\b", t) and re.search(r"\b(?:where|find|what|don't know|do not know|cannot see|can't see|don't have)\b", t):
        return Recognition(Intent.INFO, "booking.reference_help")
    if re.search(r"\b(?:have you (?:booked|scheduled|reserved|cancelled|canceled|rescheduled)|did you (?:book|schedule|reserve|cancel|reschedule)|is (?:my|the|that) (?:booking|appointment) (?:confirmed|booked|cancelled|canceled)|booking status)\b", t):
        return Recognition(Intent.INFO, "booking.status_question")
    if re.search(r"\b(?:hours|prices?|cost|how much|services|address|where are you|when do you open|what time do you (?:open|close)|what do you offer)\b", t) or re.search(rf"\bhow (?:(?:do|can|could) i |to )(?:cancel|book|reschedule|change|adjust|update|shift|(?:make|arrange)\s+{BOOKING_OBJECT})\b", t):
        return Recognition(Intent.INFO, "business.question")
    actions = []
    if re.search(r"\b(?:cancel|remove|delete)\s+(?:(?:my|the|an|this|that|a)\s+)?(?:(?:new|existing|confirmed|original|previous)\s+)?(?:appointment|booking|reservation|it|that|nl[- ]?[a-z0-9]{8})\b|^cancel$", t):
        actions.append(Intent.CANCEL)
    schedule_request = rf"\b(?:change|adjust|update|shift)\s+(?:{EXISTING_OBJECT}\b|(?:(?:my|the|this|that)\s+)?{SCHEDULE_FIELD}\s+(?:of|for|on)\s+{EXISTING_OBJECT}\b)"
    # A bounded command-shaped transcript may use a past-tense spelling.
    # Reports such as 'they rescheduled' are not turned into new commands.
    repaired_command = rf"^(?:(?:and|please)\s+)*(?:rescheduled|re schedule)\s+(?:{EXISTING_OBJECT}|it)\b"
    if re.search(r"\b(?:reschedule|move)\b", t) or re.search(schedule_request, t) or re.search(repaired_command, t):
        actions.append(Intent.RESCHEDULE)
    if re.search(r"\b(?:availability|available|openings?|free slots?)\b", t):
        actions.append(Intent.AVAILABILITY)
    booking_command = r"^(?:(?:yes|yeah|yep|okay|ok|sure|please)[,\s]+)*(?:book|schedule|reserve)\b"
    booking_request = rf"\b(?:to|can you|could you|please|let's|and) (?:book|schedule|reserve)\b|\b(?:make|arrange)\s+{BOOKING_OBJECT}\b"
    service_request = r"\b(?:want|need|like|can i|could i)\s+(?:you to\s+|to\s+)?(?:(?:make|book|get|have|schedule|reserve)\s+)?(?:a|an)\s+(?:haircut|hair cut|hair (?:and|plus) beard(?: appointment)?|beard trim|appointment)\b"
    fit_request = r"^(?:(?:please|hi|hello) )?(?:can|could|would) you (?:please )?(?:fit|squeeze) me in\b"
    if re.search(fit_request, t) or re.search(booking_command, t) or re.search(booking_request, t) or re.search(service_request, t):
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



def customer_name(text: str, *, expecting_name: bool) -> str | None:
    """Extract an entire name slot using bounded, anchored request wrappers."""
    candidate = intent_text(text)
    candidate = re.sub(r"^(?:(?:actually|please)[,\s]+)+", "", candidate)
    request_prefix = r"^(?:could you|can you|would you|i want you to|you should|you can)\s+(?:please\s+)?"
    requested = bool(re.match(request_prefix, candidate))
    candidate = re.sub(request_prefix, "", candidate)
    explicit = re.fullmatch(
        r"(?:use (?:(?:the|my) )?name(?: (?:is|of))?"
        rf"|{NAME_PREPOSITION}"
        r"|put (?:it|(?:(?:the|my) )?(?:booking|appointment)) under(?: the name)?"
        r"|under(?: the name)?|(?:my|the) name is|name is|name's|i am|i'm|call me)\s+(.+)",
        candidate,
    )
    if explicit:
        candidate = explicit[1]
    elif expecting_name or (requested and candidate.startswith("use ")):
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


def explicit_name_clause(text: str) -> tuple[str | None, str, str | None]:
    """Consume marked names independently of calendar/service validation.

    Inline clauses require a creation request, a name marker, and a bounded
    separator before subsequent details. Unmarked words never infer a name.
    """
    original = clean = normalize(text)
    whole_name = customer_name(text, expecting_name=False)
    if whole_name:
        return whole_name, "", None
    if recognize(text).intent != Intent.CREATE:
        return None, clean, None
    marker = rf"\b(?:{NAME_PREPOSITION}|under the name|use (?:(?:the|my) )?name(?: (?:is|of))?|my name is|the name is|call me)\s+"
    boundary = (
        r"\s+(?:and\s+)?(?:for|on|at)\b|,\s*"
        r"|\s+and\s+(?=\d|(?:today|tomorrow|next|haircut|hair|beard|classic|combo|use|with|under)\b)"
        r"|\s+(?=(?:today|tomorrow|yesterday|next)\b)"
    )
    names = set()
    issue = None
    for match in re.finditer(marker, original):
        # A negated name instruction must never supply an affirmative value.
        if re.search(r"\b(?:not|never|don't|do not)\b", clean[:match.start()]):
            issue = "Which fictional customer name should I use instead?"
            continue
        remainder = original[match.end():]
        separator = re.search(boundary, remainder)
        end = match.end() + (separator.start() if separator else len(remainder))
        value = customer_name("use name " + original[match.end():end], expecting_name=False)
        if value:
            names.add(value)
            clean = clean[:match.start()] + " " * (end - match.start()) + clean[end:]
        else:
            issue = "Please give one fictional customer name, for example 'use the name Alex Example'."
    if len(names) > 1:
        issue = "I heard more than one name. Please give one fictional customer name."
    return (next(iter(names)) if len(names) == 1 and not issue else None), clean, issue


def extract(text: str, now: datetime, *, expecting_name: bool = False, expecting_time: bool = False, expecting_date: bool = False, rescheduling: bool = False) -> Extraction:
    result = Extraction()
    e, issues = result.entities, result.issues
    e.name, clean, name_issue = explicit_name_clause(text)
    if name_issue:
        issues["name"] = name_issue
    ref = re.search(r"\bnl[- ]?([a-z0-9]{8})\b", clean)
    if ref:
        e.reference = "NL-" + ref[1].upper()
    # References contain arbitrary letters/digits; never parse them as names/times.
    clean = re.sub(r"\bnl[- ]?[a-z0-9]{8}\b", "", clean)
    # In an explicit directional change, the source is not a second requested
    # value. Alternatives without a direction still trigger ambiguity below.
    if rescheduling or re.search(r"\b(?:change|move|reschedule|switch)\b", clean):
        clean = re.sub(r"\bfrom\s+.+?\s+to\s+", "to ", clean, count=1)
    e.service, service_issue = extract_service(clean)
    if service_issue:
        issues["service"] = service_issue

    calendar = extract_dates(clean, now, expecting_date=expecting_date)
    dates, date_clean = calendar.values, calendar.remainder
    if calendar.issue:
        issues["date"] = calendar.issue
    if len(dates) == 1:
        e.date = next(iter(dates))

    clock = extract_clock(clean, date_clean, expecting_time=expecting_time)
    e.time, e.period = clock.time, clock.period
    if clock.issue:
        issues["time"] = clock.issue

    # Bare-name fallback requires a name context and no competing slot values.
    # An explicit name clause above survives issues in any other field.
    if e.name is None and not (dates or e.time or e.period or e.service or e.reference or issues):
        e.name = customer_name(text, expecting_name=expecting_name)
    for key in issues:
        setattr(e, key, None)
    return result
