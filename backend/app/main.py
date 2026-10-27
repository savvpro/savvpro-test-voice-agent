from __future__ import annotations

import re
from typing import Literal, TypedDict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

SERVICES = ("full groom", "bath", "haircut", "nail trim")
SERVICE_ALIASES = {
    "full groom": ("full groom", "full grooming", "grooming"),
    "bath": ("bath", "bathing"),
    "haircut": ("haircut", "hair cut"),
    "nail trim": ("nail trim", "nail clipping", "nail clip"),
}
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
WEEKDAY_ALIASES = {
    "mon": "monday",
    "tue": "tuesday",
    "tues": "tuesday",
    "wed": "wednesday",
    "thu": "thursday",
    "thur": "thursday",
    "thurs": "thursday",
    "fri": "friday",
    "sat": "saturday",
    "sun": "sunday",
}
AVAILABLE_SLOTS = {
    ("tuesday", "10:00 AM"),
    ("tuesday", "2:00 PM"),
    ("wednesday", "10:00 AM"),
    ("wednesday", "4:00 PM"),
    ("friday", "1:00 PM"),
    ("saturday", "10:00 AM"),
    ("saturday", "2:00 PM"),
}
BOOKING_FIELDS = ("service", "pet_name", "day", "time", "owner_name")
Intent = Literal["book", "reschedule", "update", "cancel", "none"]
Status = Literal["collecting", "confirming", "booked", "cancelled", "idle"]


class ConversationState(TypedDict):
    intent: Intent
    status: Status
    booking: dict[str, str]
    pending_action: Literal["", "cancel", "confirm_booking", "confirm_reschedule", "confirm_update"]
    reschedule_original: dict[str, str] | None


class TurnRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)


class TurnResponse(BaseModel):
    session_id: str
    reply: str
    intent: Intent
    current_step: str
    status: Status
    booking: dict[str, str]
    available_slots: list[str]


sessions: dict[str, ConversationState] = {}


def _new_session() -> ConversationState:
    return {
        "intent": "none",
        "status": "idle",
        "booking": {},
        "pending_action": "",
        "reschedule_original": None,
    }


def _find_day(text: str) -> str | None:
    match = re.search(r"\b(" + "|".join(WEEKDAYS) + r")\b", text, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    match = re.search(r"\b(" + "|".join(WEEKDAY_ALIASES) + r")\b", text, re.IGNORECASE)
    if not match:
        return None
    day = match.group(1).lower()
    return WEEKDAY_ALIASES.get(day, day)


def _find_time(text: str) -> str | None:
    match = re.search(
        r"\b(?:at\s*)?(\d{1,2})(?::(00|30))?\s*([ap])\.?m\.?(?!\w)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    hour = int(match.group(1))
    if not 1 <= hour <= 12:
        return None
    minute = match.group(2) or "00"
    return f"{hour}:{minute} {match.group(3).upper()}M"


def _extract_fields(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    lowered = text.lower()

    service = next(
        (
            canonical
            for canonical in SERVICES
            if any(
                re.search(r"\b" + re.escape(alias) + r"\b", lowered)
                for alias in SERVICE_ALIASES[canonical]
            )
        ),
        None,
    )
    if service is not None:
        found["service"] = service

    day = _find_day(text)
    if day:
        found["day"] = day

    time = _find_time(text)
    if time:
        found["time"] = time

    pet_match = re.search(
        r"\b(?:for\s+my\s+pet|my\s+pet)\s+([a-z][a-z'-]*)\b"
        r"|\bfor\s+([a-z][a-z'-]*)\b",
        text,
        re.IGNORECASE,
    )
    if pet_match:
        candidate = (pet_match.group(1) or pet_match.group(2)).lower()
        if (
            candidate not in SERVICES
            and candidate not in WEEKDAYS
            and candidate not in WEEKDAY_ALIASES
            and candidate not in {"me", "my"}
        ):
            found["pet_name"] = candidate.title()

    owner_match = re.search(r"\bmy name is\s+([a-z][a-z'-]*)\b", text, re.IGNORECASE)
    if owner_match:
        found["owner_name"] = owner_match.group(1).title()

    pet_name_match = re.search(
        r"\bmy pet(?:'s|s)? name is\s+([a-z][a-z'-]*)\b",
        text,
        re.IGNORECASE,
    )
    if pet_name_match:
        found["pet_name"] = pet_name_match.group(1).title()

    return found


def _add_contextual_name(found: dict[str, str], text: str, missing: str | None) -> None:
    if missing not in {"pet_name", "owner_name"} or found.get(missing):
        return

    answer = re.fullmatch(
        r"\s*(?:it's|it is|this is|i am|i'm|called|named)?\s*"
        r"([a-z][a-z'-]*(?:\s+[a-z][a-z'-]*)?)\s*[.!]?\s*",
        text,
        re.IGNORECASE,
    )
    if not answer:
        return

    name = answer.group(1).strip()
    if name.lower() not in SERVICES and name.lower() not in WEEKDAYS:
        found[missing] = name.title()


def _next_missing(booking: dict[str, str]) -> str | None:
    return next((field for field in BOOKING_FIELDS if not booking.get(field)), None)


def _question_for(field: str) -> str:
    return {
        "service": "What grooming service would you like: a bath, haircut, nail trim, or full groom?",
        "pet_name": "What is your pet's name?",
        "day": "Which day would you prefer?",
        "time": "What time works for you?",
        "owner_name": "What is your name for the appointment?",
    }[field]


def _slot_label(day: str, time: str) -> str:
    return f"{day.title()} at {time}"


def _booking_summary(booking: dict[str, str]) -> str:
    return (
        f"a {booking['service']} for {booking['pet_name']} on "
        f"{_slot_label(booking['day'], booking['time'])}, under {booking['owner_name']}"
    )


def _available_slot_labels() -> list[str]:
    return [_slot_label(day, time) for day, time in sorted(AVAILABLE_SLOTS)]


def _begin_booking(session: ConversationState, intent: Literal["book", "reschedule"]) -> str:
    session["intent"] = intent
    session["status"] = "collecting"
    return ""


def _is_yes(answer: str) -> bool:
    return answer in {"yes please", "confirm", "that's right", "book it", "do it"} or bool(
        re.fullmatch(r"(?:yes|yep|yeah)(?:\s+(?:yes|yep|yeah|please))*", answer)
    )


def _is_booking_request(text: str) -> bool:
    return bool(
        re.search(
            r"\b(book|schedule|appointment|groom|grooming|spa|bath|bathing|"
            r"haircut|hair\s+cut|nail\s+trim|nail\s+clipping)\b",
            text,
            re.IGNORECASE,
        )
    )


def _handle_turn(session_id: str, text: str) -> TurnResponse:
    session = sessions.setdefault(session_id, _new_session())
    booking = session["booking"]
    lowered = text.lower().strip()
    normalized = re.sub(r"[,.!?]+", " ", lowered).strip()
    intent = str(session["intent"])
    reply = ""

    if session["pending_action"] == "cancel":
        if _is_yes(normalized):
            booking.clear()
            session["status"] = "cancelled"
            session["intent"] = "cancel"
            session["pending_action"] = ""
            session["reschedule_original"] = None
            reply = "Your appointment has been cancelled. Would you like to book another grooming visit?"
        elif normalized in {"no", "no thanks", "keep it", "nope", "not now"}:
            if session["reschedule_original"] is not None:
                session["booking"] = session["reschedule_original"]
                session["reschedule_original"] = None
            session["status"] = "booked"
            session["pending_action"] = ""
            reply = "No problem—your appointment is still booked."
        else:
            reply = "Please say yes to cancel the appointment, or no to keep it."
        return _make_response(session_id, session, reply)

    if session["pending_action"] in {"confirm_booking", "confirm_reschedule", "confirm_update"}:
        pending_action = session["pending_action"]
        if _is_yes(normalized):
            session["pending_action"] = ""
            session["status"] = "booked"
            session["reschedule_original"] = None
            if pending_action == "confirm_reschedule":
                reply = f"Your appointment has been moved to {_slot_label(booking['day'], booking['time'])}."
            elif pending_action == "confirm_update":
                reply = f"Your appointment details have been updated. The appointment is for {booking['pet_name']}."
            else:
                reply = (
                    f"You're all set! {booking['owner_name']}'s appointment for {booking['pet_name']} "
                    f"({booking['service']}) is booked for {_slot_label(booking['day'], booking['time'])}."
                )
            return _make_response(session_id, session, reply)

        if normalized in {"no", "no thanks", "nope", "don't book", "do not book", "not yet"}:
            session["pending_action"] = ""
            if pending_action in {"confirm_reschedule", "confirm_update"}:
                original = session["reschedule_original"]
                if original is not None:
                    session["booking"] = original
                session["reschedule_original"] = None
                session["status"] = "booked"
                reply = "No changes made. Your original appointment is still booked."
            else:
                booking.clear()
                session["intent"] = "none"
                session["status"] = "idle"
                reply = "No problem—I haven't booked anything. You can start a new appointment whenever you're ready."
            return _make_response(session_id, session, reply)

        if re.search(r"\b(cancel|never mind|nevermind)\b", lowered):
            session["pending_action"] = ""
            if pending_action in {"confirm_reschedule", "confirm_update"}:
                original = session["reschedule_original"]
                if original is not None:
                    session["booking"] = original
                session["reschedule_original"] = None
                session["status"] = "booked"
                reply = "No changes made. Your original appointment is still booked."
            else:
                booking.clear()
                session["intent"] = "none"
                session["status"] = "idle"
                reply = "Okay, I haven't booked anything. Let me know if you'd like to start over."
            return _make_response(session_id, session, reply)

        changes = _extract_fields(text)
        if pending_action == "confirm_reschedule":
            changes = {key: value for key, value in changes.items() if key in {"day", "time"}}
        if not changes:
            reply = "Please say yes to confirm, or tell me what you'd like to change."
            return _make_response(session_id, session, reply)
        session["pending_action"] = ""
        session["status"] = "collecting"

    if re.search(r"\b(cancel|取消)\b", lowered):
        if session["status"] == "booked" or session["reschedule_original"] is not None:
            if session["reschedule_original"] is not None:
                session["booking"] = session["reschedule_original"]
            session["intent"] = "cancel"
            session["pending_action"] = "cancel"
            reply = "Are you sure you want to cancel your appointment? Please say yes or no."
        else:
            session["intent"] = "cancel"
            reply = "There is no active appointment to cancel. You can ask me to book one."
        return _make_response(session_id, session, reply)

    if re.search(r"\b(reschedule|change|move)\b", lowered) and session["status"] == "booked":
        session["reschedule_original"] = dict(booking)
        session["intent"] = "reschedule"
        session["status"] = "collecting"
        reply = "Sure. Tell me the new day and time you'd like."
        found = _extract_fields(text)
        found.pop("service", None)
        found.pop("pet_name", None)
        found.pop("owner_name", None)
        booking.update(found)
        if booking.get("day") and booking.get("time"):
            reply = _finish_reschedule(session, booking)
        return _make_response(session_id, session, reply)

    if session["status"] == "booked":
        if re.fullmatch(r"(?:no thanks(?:,?\s*)?)?(?:bye|goodbye|that's all|that is all)", normalized):
            return _make_response(
                session_id,
                session,
                "Thanks for choosing PawPal! Your appointment is still booked. Goodbye!",
            )
        if normalized in {"no thanks", "that's all", "that is all", "goodbye", "bye"}:
            return _make_response(
                session_id,
                session,
                "Thanks for choosing PawPal! Your appointment is still booked. Goodbye!",
            )

        changes = _extract_fields(text)
        if changes:
            session["reschedule_original"] = dict(booking)
            session["intent"] = "update"
            session["status"] = "collecting"
            booking.update(changes)
        elif re.search(r"\b(book|schedule|appointment|groom)\b", lowered):
            session["intent"] = "book"
            session["status"] = "collecting"
            session["reschedule_original"] = None
            booking.clear()
        else:
            return _make_response(
                session_id,
                session,
                "Your appointment is booked. You can ask me to reschedule or cancel it.",
            )

    if intent == "none" or session["status"] in {"idle", "cancelled"}:
        if _is_booking_request(text):
            _begin_booking(session, "book")
            if re.search(r"\bspa\b", lowered) and not _extract_fields(text).get("service"):
                reply = "I can book a bath, haircut, nail trim, or full groom. Which service would you like?"
        else:
            reply = (
                "Hi, I'm PawPal. I can book, reschedule, or cancel a grooming appointment. "
                "To book, tell me the service, your pet's name, and a day and time—for example, "
                "\"Full groom for Sasha Friday at 1 PM.\" What would you like to do?"
            )
            return _make_response(session_id, session, reply)

    missing = _next_missing(booking)
    found = _extract_fields(text)
    _add_contextual_name(found, text, missing)
    booking.update(found)
    missing = _next_missing(booking)
    if missing:
        if not reply:
            reply = _question_for(missing)
    else:
        day = booking["day"]
        time = booking["time"]
        if (day, time) not in AVAILABLE_SLOTS:
            if session["intent"] == "update":
                original = session["reschedule_original"]
                if original is not None:
                    booking.clear()
                    booking.update(original)
                session["status"] = "booked"
                session["reschedule_original"] = None
                reply = (
                    f"That time isn't available, so your existing appointment is unchanged. "
                    f"Available sample openings: {', '.join(_available_slot_labels())}."
                )
                return _make_response(session_id, session, reply)
            choices = ", ".join(_available_slot_labels())
            reply = f"Sorry, {day.title()} at {time} isn't available. Please choose one of these sample openings: {choices}."
        elif session["intent"] == "reschedule":
            reply = _finish_reschedule(session, booking)
        elif session["intent"] == "update":
            session["status"] = "confirming"
            session["pending_action"] = "confirm_update"
            reply = f"Please confirm the updated details: {_booking_summary(booking)}. Should I save these changes?"
        else:
            session["status"] = "confirming"
            session["pending_action"] = "confirm_booking"
            reply = f"Please confirm: {_booking_summary(booking)}. Should I book it?"

    return _make_response(session_id, session, reply)


def _finish_reschedule(session: ConversationState, booking: dict[str, str]) -> str:
    day = booking["day"]
    time = booking["time"]
    if (day, time) not in AVAILABLE_SLOTS:
        original = session["reschedule_original"]
        if original is not None:
            booking["day"] = original["day"]
            booking["time"] = original["time"]
        return (
            f"Sorry, {day.title()} at {time} isn't available. Your original appointment is unchanged. "
            f"Choose one of these sample openings: {', '.join(_available_slot_labels())}."
        )
    session["status"] = "confirming"
    session["pending_action"] = "confirm_reschedule"
    return f"Please confirm: move your appointment to {_slot_label(day, time)}. Should I make that change?"


def _make_response(session_id: str, session: ConversationState, reply: str) -> TurnResponse:
    booking = session["booking"]
    next_field = _next_missing(booking)
    current_step = (
        "confirm_cancel"
        if session["pending_action"] == "cancel"
        else "confirm_booking"
        if session["pending_action"] == "confirm_booking"
        else "confirm_reschedule"
        if session["pending_action"] == "confirm_reschedule"
        else "confirm_update"
        if session["pending_action"] == "confirm_update"
        else next_field
        or (
            "complete"
            if session["status"] == "booked"
            else "reschedule_slot"
            if session["status"] == "collecting" and session["intent"] == "reschedule"
            else "choose_slot"
            if session["status"] == "collecting"
            else "start"
        )
    )
    return TurnResponse(
        session_id=session_id,
        reply=reply,
        intent=session["intent"],
        current_step=current_step,
        status=session["status"],
        booking=dict(booking),
        available_slots=_available_slot_labels(),
    )


app = FastAPI(title="PawPal Assistant API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/turn", response_model=TurnResponse)
def turn(request: TurnRequest) -> TurnResponse:
    return _handle_turn(request.session_id, request.message.strip())
