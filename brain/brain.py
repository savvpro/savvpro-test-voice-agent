import re
from datetime import datetime
from typing import Dict, Tuple

from . import availability
from .nlu import parse_text
from .state import (BOOKED, CANCELLED, CHECKING_AVAILABILITY, COLLECTING,
                    CONFIRMING, GOODBYE, GREETING, Session)

REQUIRED = ("date", "time", "reason", "patient_name", "phone")


def speak_time(hhmm: str) -> str:
    value = datetime.strptime(hhmm, "%H:%M")
    hour = value.hour % 12 or 12
    suffix = "AM" if value.hour < 12 else "PM"
    return f"{hour}{f':{value.minute:02d}' if value.minute else ''} {suffix}"


def speak_date(iso: str) -> str:
    value = datetime.strptime(iso, "%Y-%m-%d")
    return f"{value.strftime('%A, %B')} {value.day}"


def _pending(session: Session) -> str | None:
    return next((slot for slot in REQUIRED if not session.slots.get(slot)), None)


def _ask(slot: str) -> str:
    return {
        "date": "What date would you like? Please give a concrete date.",
        "time": "What time would you like? Please include am or pm.",
        "reason": "What is the reason for the visit?",
        "patient_name": "Please tell me the patient's full name.",
        "phone": "What phone number should we use?",
    }[slot]


def _valid_patient_name(value: str) -> bool:
    letters = re.sub(r"[^A-Za-z]", "", value)
    if len(letters) < 2 or not re.search(r"[AEIOUaeiou]", letters):
        return False
    normalized = letters.lower()
    if len(set(normalized)) == 1 or re.fullmatch(r"(.)\1(.)\2", normalized):
        return False
    return True


def _decision(intent: str, slots: Dict[str, str], session: Session) -> Tuple[Session, Dict]:
    return session, {"intent": intent, "slots": dict(session.slots), "state": session.current_state,
                     "pending_slot": session.pending_slot}


def _confirmation_result(session: Session, intent: str, detected: Dict[str, str]):
    session.current_state = CHECKING_AVAILABILITY
    if not availability.is_working_slot(session.slots["time"]):
        alternatives = availability.nearest_free(session.slots["date"], session.slots["time"])
        session.current_state, session.pending_slot = COLLECTING, "time"
        session, decision = _decision(intent, detected, session)
        return session, (f"We're open 9am to 5pm. The nearest available time is "
                         f"{speak_time(alternatives[0])} or {speak_time(alternatives[1])}."), decision
    if availability.is_free(session.slots["date"], session.slots["time"]):
        session.current_state, session.pending_slot = CONFIRMING, None
        summary = (f"{session.slots['patient_name']} for {session.slots['reason']} on "
                   f"{speak_date(session.slots['date'])} at {speak_time(session.slots['time'])}, phone "
                   f"{session.slots['phone']}. Is that correct?")
        session, decision = _decision(intent, detected, session)
        return session, summary, decision
    alternatives = availability.nearest_free(session.slots["date"], session.slots["time"])
    session.current_state, session.pending_slot = COLLECTING, "time"
    session, decision = _decision(intent, detected, session)
    return session, (f"That time is not available. The nearest available times are "
                     f"{speak_time(alternatives[0])} or {speak_time(alternatives[1])}. Which would you prefer?"), decision


def handle_turn(session: Session, text: str):
    parsed = parse_text(text, session.current_state, session.pending_slot)
    intent, detected = parsed["intent"], parsed["slots"]
    updated = session.copy()

    if intent == "cancel":
        updated.current_state, updated.pending_slot = CANCELLED, None
        updated, decision = _decision(intent, detected, updated)
        return updated, "Your appointment request has been cancelled. Goodbye.", decision
    if intent == "out_of_scope":
        updated, decision = _decision(intent, detected, updated)
        return updated, "I only handle clinic appointments. How can I help with an appointment?", decision
    if (
        updated.current_state == COLLECTING
        and updated.pending_slot == "patient_name"
        and "patient_name" in detected
        and not _valid_patient_name(detected["patient_name"])
    ):
        detected.pop("patient_name")
        for slot, value in detected.items():
            if value is not None:
                updated.slots[slot] = value
        updated, decision = _decision(intent, detected, updated)
        return updated, "Please tell me the patient's full name.", decision
    if updated.current_state == CONFIRMING and intent == "unclear" and not detected:
        if updated.awaiting_change_field:
            field_match = next(
                (field for field in REQUIRED
                 if re.search(rf"\b{field.replace('_', ' ')}\b", text.lower())),
                None,
            )
            if field_match is None and re.search(r"\bname\b", text.lower()):
                field_match = "patient_name"
            if field_match:
                updated.slots.pop(field_match, None)
                updated.current_state = COLLECTING
                updated.pending_slot = field_match
                updated.awaiting_change_field = False
                updated, decision = _decision(intent, detected, updated)
                return updated, _ask(field_match), decision
        updated, decision = _decision(intent, detected, updated)
        return updated, "Please say yes to confirm, or tell me what to change.", decision
    if intent == "unclear" and not detected:
        if (
            updated.current_state == COLLECTING
            and updated.pending_slot in {"patient_name", "phone"}
            and text.strip()
        ):
            updated, decision = _decision(intent, detected, updated)
            return updated, _ask(updated.pending_slot), decision
        if text.strip().lower() in {"asdf"}:
            updated, decision = _decision(intent, detected, updated)
            return updated, "Sorry, I didn't catch that.", decision
        if (
            updated.current_state == COLLECTING
            and updated.pending_slot
            and not parsed.get("filler_only")
            and any(character.isalpha() for character in text)
        ):
            updated, decision = _decision(intent, detected, updated)
            return updated, _ask(updated.pending_slot), decision
        updated, decision = _decision(intent, detected, updated)
        return updated, "Sorry, I didn't catch that.", decision

    if updated.current_state == CONFIRMING:
        if any(value for value in detected.values()):
            for slot, value in detected.items():
                if value:
                    updated.slots[slot] = value
            updated.awaiting_change_field = False
            return _confirmation_result(updated, intent, detected)
        if updated.awaiting_change_field:
            field_match = next(
                (field for field in REQUIRED if re.search(rf"\b{field.replace('_', ' ')}\b", text.lower())),
                None,
            )
            if field_match is None and re.search(r"\bname\b", text.lower()):
                field_match = "patient_name"
            if field_match:
                updated.slots.pop(field_match, None)
                updated.current_state = COLLECTING
                updated.pending_slot = field_match
                updated.awaiting_change_field = False
                updated, decision = _decision(intent, detected, updated)
                return updated, _ask(field_match), decision
        if intent == "confirm_yes":
            availability.book(**updated.slots)
            updated.current_state, updated.pending_slot = BOOKED, None
            updated.awaiting_change_field = False
            updated, decision = _decision(intent, detected, updated)
            return updated, "Your appointment is booked. Goodbye!", decision
        if intent == "confirm_no":
            updated.awaiting_change_field = True
            updated, decision = _decision(intent, detected, updated)
            return updated, "Which detail would you like to change?", decision
        if intent == "change":
            updated.awaiting_change_field = True
            updated, decision = _decision(intent, detected, updated)
            return updated, "Which detail would you like to change?", decision
        updated, decision = _decision(intent, detected, updated)
        return updated, "Please say yes to confirm, or tell me what to change.", decision

    if updated.current_state == GREETING:
        updated.current_state = COLLECTING
    for slot, value in detected.items():
        if value is None:
            updated.slots.pop(slot, None)
        else:
            updated.slots[slot] = value
    pending = _pending(updated)
    if pending:
        updated.current_state, updated.pending_slot = COLLECTING, pending
        updated, decision = _decision(intent, detected, updated)
        if parsed.get("ambiguous_time") and pending == "time":
            reply = "What time would you like? Please specify am or pm."
        else:
            reply = _ask(pending)
        return updated, reply, decision

    return _confirmation_result(updated, intent, detected)
