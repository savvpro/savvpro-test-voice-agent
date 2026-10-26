import re
from datetime import datetime

from lost_property.domain.extraction import extract
from lost_property.domain.identification import identify
from lost_property.domain.matching import rank
from lost_property.domain.models import (
    Candidate,
    Conversation,
    Effect,
    Fields,
    FoundItem,
    Message,
    OutcomeKind,
    Trace,
    TurnResult,
)
from lost_property.domain.normalization import COLOURS, contains, descriptive_tokens, normalize

GREETING = (
    "Welcome to Riverside's lost-property desk. Tell me what you lost, "
    "where you last had it, and roughly when."
)
QUESTIONS = {
    "category": "What did you lose: a bag, phone, wallet, or keys?",
    "colour": "What colour is it? It's okay if you're not sure.",
    "location": "Where in the mall did you last have it?",
    "lost_date": "What day did you lose it? Say yesterday or a date such as 25 October.",
    "brand": "Do you know the brand? You can say you don't know.",
    "description": "How would you describe it? Tell me its shape, style, or details you remember.",
    "identifying": "Can you describe any distinctive marks, attachments, or something inside?",
}
AFFIRMATIVES = {"yes", "yes please", "correct", "confirm", "submit", "go ahead", "that's right"}
NEGATIVES = {"no", "no thanks", "don't", "do not", "not yet"}


def _finish(
    current: Conversation,
    text: str,
    reply: str,
    rule: str,
    inventory: list[FoundItem],
    effect: Effect | None = None,
) -> TurnResult:
    current.transcript.extend(
        [Message(role="caller", text=text), Message(role="assistant", text=reply)]
    )
    return TurnResult(
        conversation=current,
        reply=reply,
        candidates=rank(current.fields, inventory),
        effect=effect,
        trace=Trace(
            rule=rule,
            explanation={
                "cancel": "The caller ended the conversation; no new case was created.",
                "confirm": "Explicit confirmation permits the proposed database action.",
                "receipt": "Repeat the completed case without creating another case.",
                "identify": (
                    "Public evidence supports an open identifying question. "
                    "Staff review is required."
                ),
                "propose_claim": "Offer a possible-match review; only staff can approve ownership.",
                "propose_report": (
                    "Insufficient evidence for one convincing item; offer a lost report."
                ),
                "clarify": "Ask for missing or ambiguous information instead of guessing.",
                "correct": "Changed details invalidate the previous selection and confirmation.",
            }.get(rule, "Follow explicit rules and preserve the caller's supplied facts."),
        ),
    )


def _ask(current: Conversation, field: str) -> str:
    current.asked = field
    current.attempts[field] = current.attempts.get(field, 0) + 1
    return QUESTIONS[field]


def _proposal(current: Conversation, kind: OutcomeKind) -> str:
    current.state = "confirming"
    current.proposal = kind
    current.asked = None
    fields = current.fields
    description = " ".join(part for part in (fields.colour, fields.category) if part) or "lost item"
    location = f" near {fields.location}" if fields.location else ""
    lost = f", lost on {fields.lost_date}" if fields.lost_date else ""
    action = "a possible-match claim for staff review" if kind == "claim" else "a lost-item report"
    return (
        f"I can submit {action} for your {description}{location}{lost}. "
        "Staff must check ownership before releasing property. Shall I submit it?"
    )


def _update(current: Conversation, text: str, now: datetime) -> str | None:
    extracted = extract(text, now, current.asked)
    values = current.fields.model_dump()
    if any(values[name] != value for name, value in extracted.values.items()):
        current.selection = None
        current.shortlisted = []
        current.proposal = None
        current.details = ""
        current.identifying_attempts = 0
        current.state = "collecting"
    values.update(extracted.values)
    if extracted.problem:
        values[extracted.problem] = None
    values["uncertain"] = sorted(
        (set(current.fields.uncertain) - extracted.values.keys()) | set(extracted.uncertain)
    )
    values["unknown"] = sorted(
        (set(current.fields.unknown) | set(extracted.unknown)) - extracted.values.keys()
    )
    if not extracted.unknown:
        values["description"] = f"{current.fields.description} {text}".strip()[-3000:]
        current.details = f"{current.details} {text}".strip()[-3000:]
    current.fields = Fields.model_validate(values)
    return extracted.problem


def _next_field(
    current: Conversation, candidates: list[Candidate], inventory: list[FoundItem]
) -> str | None:
    fields = current.fields
    available = [
        name
        for name in ("colour", "location", "lost_date", "brand", "description")
        if name not in fields.unknown
        and current.attempts.get(name, 0) < 2
        and (name in fields.uncertain or not getattr(fields, name))
    ]
    if (
        not descriptive_tokens(fields.description)
        and "description" not in fields.unknown
        and current.attempts.get("description", 0) < 2
        and "description" not in available
    ):
        available.append("description")
    eligible = {candidate.item_id for candidate in candidates[:3] if candidate.score >= 40}
    items = [item for item in inventory if item.id in eligible]
    if len(items) > 1 and available:

        def distinct(name: str) -> int:
            attribute = "found_date" if name == "lost_date" else name
            return len({getattr(item, attribute) for item in items if getattr(item, attribute)})

        return max(available, key=distinct)
    return next(
        (
            name
            for name in ("description", "lost_date", "colour", "location", "brand")
            if name in available
        ),
        None,
    )


def _claim_inventory(current: Conversation, inventory: list[FoundItem]) -> list[FoundItem]:
    candidates = [
        candidate for candidate in rank(current.fields, inventory) if candidate.score >= 40
    ]
    if not candidates or candidates[0].score < 55 or candidates[0].item_id != current.selection:
        return []
    if len(candidates) > 1 and candidates[0].score - candidates[1].score < 15:
        return []
    return [item for item in inventory if item.id == current.selection]


def respond(
    state: Conversation, text: str, inventory: list[FoundItem], now: datetime
) -> TurnResult:
    current = state.model_copy(deep=True)
    current.version += 1
    value = normalize(text)
    correction = any(
        contains(value, phrase)
        for phrase in ("actually", "instead", "i meant", "correction", "not")
    )
    direct_colour = re.search(
        r"\b(?:it is|it's|it was|the (?:bag|backpack|phone|wallet|keys) is)\s+(?:"
        + "|".join(re.escape(colour) for colour in COLOURS)
        + r")\b",
        value,
    )
    correction = correction or direct_colour is not None
    if value in ("cancel", "stop", "goodbye", "bye", "end conversation"):
        current.state = "cancelled"
        current.proposal = None
        reply = "I've ended this conversation. No new request was submitted."
        if current.receipt:
            reply += " Your existing case remains with staff; contact the desk for changes."
        return _finish(current, text, reply, "cancel", inventory)
    if current.restart_pending:
        current.restart_pending = False
        if value in AFFIRMATIVES:
            current = Conversation(
                version=current.version,
                search_number=current.search_number + 1,
                transcript=current.transcript,
            )
            return _finish(current, text, GREETING, "restart", inventory)
        reply = "I've kept your details. " + QUESTIONS.get(current.asked or "category", GREETING)
        return _finish(current, text, reply, "keep", inventory)
    if value in ("restart", "start again", "new search", "start over"):
        if current.fields.category or current.receipt:
            current.restart_pending = True
            reply = (
                "Start a new search and discard these search details? "
                "Submitted cases remain with staff."
            )
            return _finish(current, text, reply, "restart_confirm", inventory)
        return _finish(current, text, GREETING, "restart", inventory)
    if value in ("repeat", "say that again", "repeat please"):
        reply = (
            current.transcript[-1].text
            if current.transcript
            else QUESTIONS.get(current.asked or "category", GREETING)
        )
        return _finish(current, text, reply, "repeat", inventory)
    if value in ("help", "what can you do"):
        return _finish(
            current,
            text,
            "I help find bags, phones, wallets, and keys lost at Riverside Mall. "
            "Describe your item, correct a detail, or say repeat, restart, or cancel.",
            "help",
            inventory,
        )
    if current.state == "completed" and current.receipt:
        return _finish(
            current,
            text,
            f"Your reference is {current.receipt.reference}. Staff will review it. "
            "Say new search to find another item.",
            "receipt",
            inventory,
        )
    if current.state == "cancelled":
        return _finish(
            current,
            text,
            "This conversation has ended. Say restart to begin a new search.",
            "cancelled",
            inventory,
        )
    preferences = {
        "option 1": 0,
        "the first one": 0,
        "option 2": 1,
        "the second one": 1,
        "option 3": 2,
        "the third one": 2,
    }
    if value in preferences and current.state in ("collecting", "disambiguating", "identifying"):
        index = preferences[value]
        if index < len(current.shortlisted):
            current.selection = current.shortlisted[index]
            question = QUESTIONS.get(current.asked or "description", QUESTIONS["description"])
            return _finish(
                current,
                text,
                "I've noted that possibility. I still need a few details. " + question,
                "candidate_preference",
                inventory,
            )
    if current.state == "confirming" and not correction:
        if value in AFFIRMATIVES and current.proposal:
            effect = Effect(
                kind=current.proposal,
                item_id=current.selection if current.proposal == "claim" else None,
            )
            return _finish(current, text, "Submitting your request.", "confirm", inventory, effect)
        if value in NEGATIVES:
            current.proposal = None
            current.state = "collecting"
            return _finish(
                current,
                text,
                "Nothing was submitted. Tell me what to change, or say cancel.",
                "decline",
                inventory,
            )
        if not extract(text, now).values:
            return _finish(
                current,
                text,
                "Say yes to submit, no to keep searching, or tell me what to change.",
                "confirm_clarify",
                inventory,
            )
    if current.state == "identifying" and not correction:
        current.identifying_attempts += 1
        current.details = f"{current.details} {text}"[-3000:]
        eligible = _claim_inventory(current, inventory)
        selected = identify(current.details, eligible)
        if selected:
            current.selection = selected
            return _finish(current, text, _proposal(current, "claim"), "propose_claim", inventory)
        if current.identifying_attempts >= 2:
            current.selection = None
            return _finish(
                current, text, _proposal(current, "lost_report"), "propose_report", inventory
            )
        reply = (
            "Can you describe another distinctive feature or something inside? "
            "If you don't know, I can record a report."
        )
        return _finish(current, text, reply, "identify", inventory)
    if correction:
        current.selection = None
        current.proposal = None
        current.details = ""
        current.state = "collecting"
    problem = _update(current, text, now)
    if (
        problem == "category"
        or not current.fields.category
        or "category" in current.fields.uncertain
    ):
        if current.attempts.get("category", 0) >= 2:
            current.state = "cancelled"
            return _finish(
                current,
                text,
                "I can currently help with bags, phones, wallets, and keys. "
                "For other items, please contact the mall information desk. "
                "Say restart to begin again.",
                "unsupported_category",
                inventory,
            )
        return _finish(current, text, _ask(current, "category"), "clarify", inventory)
    if problem:
        return _finish(
            current,
            text,
            "I need to clarify that detail. " + _ask(current, problem),
            "clarify",
            inventory,
        )
    matches = rank(current.fields, inventory)
    convincing = [candidate for candidate in matches if candidate.score >= 40]
    current.shortlisted = [candidate.item_id for candidate in convincing[:3]]
    extra = any(
        getattr(current.fields, name) and name not in current.fields.uncertain
        for name in ("colour", "brand", "location", "lost_date")
    )
    margin = len(convincing) < 2 or convincing[0].score - convincing[1].score >= 15
    if convincing and convincing[0].score >= 55 and margin and extra:
        current.state = "identifying"
        current.selection = convincing[0].item_id
        current.asked = "identifying"
        selected = identify(current.details, _claim_inventory(current, inventory))
        if selected:
            current.selection = selected
            return _finish(current, text, _proposal(current, "claim"), "propose_claim", inventory)
        return _finish(current, text, QUESTIONS["identifying"], "identify", inventory)
    asked = _next_field(current, matches, inventory)
    exhausted = sum(current.attempts.values()) >= 6
    described = bool(
        descriptive_tokens(current.fields.description)
        or current.fields.colour
        or current.fields.brand
    )
    dated = bool(current.fields.lost_date) or "lost_date" in current.fields.unknown
    if exhausted or not asked or (not convincing and described and dated):
        return _finish(
            current, text, _proposal(current, "lost_report"), "propose_report", inventory
        )
    current.state = "disambiguating" if len(convincing) > 1 else "collecting"
    return _finish(
        current, text, _ask(current, asked), "correct" if correction else "clarify", inventory
    )
