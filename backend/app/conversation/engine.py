from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.booking import SERVICES, BookingStore
from app.conversation.models import Session, State, Status
from app.conversation.normalizer import normalize

TZ = ZoneInfo("America/Chicago")
FIELDS = ("name", "phone", "vehicle_year", "vehicle", "service", "date", "time")
QUESTIONS = {
    "name": "What name should I put on the appointment?",
    "phone": "What is the best 10-digit phone number?",
    "vehicle_year": "What year is the vehicle?",
    "vehicle": "What is the vehicle make and model?",
    "service": "What service does the vehicle need?",
    "date": "What date would you prefer?",
    "time": "What time would you prefer? Please include AM or PM.",
}


class ConversationEngine:
    def __init__(self, store: BookingStore, clock: Callable[[], datetime] | None = None) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(TZ))

    def create_session(self, conversation_id: str) -> Session:
        return Session(conversation_id=conversation_id, now=self.clock())

    def greeting(self, session: Session) -> dict:
        return self._response(session, "greet", "session_created", QUESTIONS["name"])

    def turn(self, session: Session, turn_id: str, expected_version: int, raw: str) -> dict:
        if turn_id in session.processed_turns:
            return session.processed_turns[turn_id]
        now = self.clock()
        if now - session.last_activity_at > timedelta(minutes=30):
            session.status, session.state = Status.EXPIRED, None
            raise SessionExpiredError
        if session.status != Status.ACTIVE:
            raise SessionTerminalError
        if expected_version != session.version:
            raise StaleTurnError

        text = normalize(raw, session.last_question)
        before = session.state.value if session.state else None
        if not text:
            session.recognition_failures += 1
            reply = "I didn't catch that. " + QUESTIONS.get(session.last_question, "Please try again.")
            return self._commit(session, turn_id, before, "reprompt", "empty_transcript", reply, {})

        candidates = self._extract(text, session, now)
        if candidates.get("non_english"):
            return self._commit(
                session,
                turn_id,
                before,
                "reprompt",
                "english_only",
                "I can only handle English for this demo. " + QUESTIONS[session.last_question],
                candidates,
            )
        if candidates.get("multiple_vehicles"):
            return self._commit(
                session,
                turn_id,
                before,
                "clarify_vehicle",
                "one_vehicle_per_call",
                "I can book one vehicle per call. Which vehicle should I use?",
                candidates,
            )
        if self._matches(text, ("goodbye", "hang up", "end call")):
            session.status, session.state = Status.ENDED, None
            return self._commit(session, turn_id, before, "end_call", "explicit_goodbye", "Goodbye.", candidates)
        if self._matches(text, ("start over", "restart")):
            session.draft.clear()
            session.retries.clear()
            session.offered_slots.clear()
            session.state, session.last_question = State.COLLECTING, "name"
            return self._commit(session, turn_id, before, "restart", "explicit_restart", QUESTIONS["name"], candidates)

        correction = bool(re.search(r"\b(change|make that|instead|not|cancel the|remove)\b", text)) and bool(candidates)
        if not correction and text in {"cancel", "never mind", "forget it"}:
            session.status, session.state = Status.ABORTED, None
            return self._commit(
                session, turn_id, before, "abort_call", "standalone_abort", "No booking was made. Goodbye.", candidates
            )

        if session.offered_slots and re.fullmatch(r"(?:option )?(one|two|three|1|2|3|first|second|third)", text):
            index = {"one": 0, "1": 0, "first": 0, "two": 1, "2": 1, "second": 1, "three": 2, "3": 2, "third": 2}[
                text.replace("option ", "")
            ]
            if index < len(session.offered_slots):
                session.draft["slot"] = session.offered_slots[index]
                session.state, session.last_question, session.expected_answer = (
                    State.CONFIRMING,
                    "confirm_booking",
                    "boolean",
                )
                return self._commit(
                    session,
                    turn_id,
                    before,
                    "select_slot",
                    "offered_slot_index",
                    self._summary(session),
                    {"offered_slot_index": index + 1},
                )

        if text in {"yes", "yeah", "correct", "confirm"}:
            if session.last_question == "confirm_service" and session.expected_answer == "boolean":
                session.draft["service"] = "general_diagnostic"
                session.last_question, session.expected_answer = "date", "text"
                return self._commit(
                    session,
                    turn_id,
                    before,
                    "accept_service_fallback",
                    "explicit_yes",
                    QUESTIONS["date"],
                    candidates,
                    {"service": "general_diagnostic"},
                )
            if session.last_question == "confirm_booking" and session.expected_answer == "boolean":
                confirmation = "SAV-" + uuid4().hex[:8].upper()
                booking = self.store.confirm(session.draft, confirmation)
                if booking:
                    session.status, session.state = Status.CONFIRMED, None
                    return self._commit(
                        session,
                        turn_id,
                        before,
                        "confirm_booking",
                        "explicit_yes",
                        f"Booked. Your confirmation number is {confirmation}.",
                        candidates,
                    )
                return self._offer_alternatives(session, turn_id, before, "slot_taken_before_confirmation")
            return self._commit(
                session,
                turn_id,
                before,
                "reprompt",
                "yes_without_boolean_question",
                QUESTIONS[session.last_question],
                candidates,
            )
        if text in {"no", "nope"} and session.last_question == "confirm_booking":
            session.state, session.last_question, session.expected_answer = State.COLLECTING, "date", "text"
            session.draft.pop("slot", None)
            return self._commit(
                session,
                turn_id,
                before,
                "revise",
                "confirmation_rejected",
                "Okay. What date should I change?",
                candidates,
            )
        if text in {"no", "nope"} and session.last_question == "confirm_service":
            session.last_question, session.expected_answer = "service", "text"
            return self._commit(
                session,
                turn_id,
                before,
                "ask_field",
                "service_fallback_rejected",
                QUESTIONS["service"],
                candidates,
            )

        if self._matches(text, ("help", "repeat", "summary")):
            reply = (
                self._summary(session)
                if "summary" in text
                else QUESTIONS.get(session.last_question, "Please continue.")
            )
            return self._commit(session, turn_id, before, "inform", "help_repeat_summary", reply, candidates)
        if "how much" in text or "price" in text:
            return self._commit(
                session,
                turn_id,
                before,
                "out_of_scope",
                "price_unavailable",
                "I can't quote prices. " + QUESTIONS[session.last_question],
                candidates,
            )
        if "car ready" in text or "vehicle ready" in text:
            return self._commit(
                session,
                turn_id,
                before,
                "out_of_scope",
                "status_lookup_unsupported",
                "I can't check repair status. " + QUESTIONS[session.last_question],
                candidates,
            )
        if "transmission" in text and "service" not in candidates:
            session.last_question, session.expected_answer = "confirm_service", "boolean"
            return self._commit(
                session,
                turn_id,
                before,
                "confirm_service_fallback",
                "unsupported_service",
                "I don't have that service listed. Should I book a general diagnostic?",
                candidates,
            )

        accepted = self._merge(session, candidates)
        if correction and any(key in accepted for key in ("date", "time", "service")):
            session.draft.pop("slot", None)
            session.offered_slots.clear()

        if candidates.get("time_ambiguous") and session.last_question == "time":
            return self._commit(
                session,
                turn_id,
                before,
                "clarify_time",
                "missing_meridiem",
                "Did you mean AM or PM?",
                candidates,
                accepted,
            )

        missing = next((field for field in FIELDS if field not in session.draft), None)
        if missing:
            if not accepted:
                retries = session.retries.get(session.last_question, 0) + 1
                session.retries[session.last_question] = retries
                if retries >= 3:
                    session.status, session.state = Status.ABORTED, None
                    return self._commit(
                        session,
                        turn_id,
                        before,
                        "escalate",
                        "retry_limit",
                        "I couldn't verify that after three tries. Please contact the shop.",
                        candidates,
                    )
            session.last_question, session.expected_answer = missing, "text"
            return self._commit(
                session, turn_id, before, "ask_field", "next_missing_field", QUESTIONS[missing], candidates, accepted
            )

        return self._resolve_slot(session, turn_id, before, candidates, accepted)

    def _extract(self, text: str, session: Session, now: datetime) -> dict:
        result: dict = {}
        if re.search(r"\b(necesito|hola|gracias|bonjour|merci)\b", text):
            result["non_english"] = True
        phone = re.search(r"\b\d{3}[ -]?\d{3}[ -]?\d{4}\b", text)
        if phone:
            result["phone"] = re.sub(r"\D", "", phone.group())
        year = re.search(r"\b(19[89]\d|20[0-2]\d)\b", text)
        if year:
            result["vehicle_year"] = int(year.group())
        services = {
            "oil": "oil_change",
            "tire": "tire_rotation",
            "brake": "brake_inspection",
            "battery": "battery_check",
            "diagnostic": "general_diagnostic",
            "squeal": "general_diagnostic",
        }
        mentioned_services = [(text.rfind(token), key) for token, key in services.items() if token in text]
        if mentioned_services:
            result["service"] = max(mentioned_services)[1]
        vehicle = re.search(r"\b(toyota|honda|ford|chevrolet|nissan)\s+([a-z0-9-]+)", text)
        makes = re.findall(r"\b(toyota|honda|ford|chevrolet|nissan)\b", text)
        if len(set(makes)) > 1:
            result["multiple_vehicles"] = sorted(set(makes))
        if vehicle:
            result["vehicle"] = vehicle.group().title()
        parsed_date = self._parse_date(text, now.date())
        if parsed_date:
            result["date"] = parsed_date.isoformat()
        parsed_time = self._parse_time(text)
        if parsed_time == "ambiguous":
            result["time_ambiguous"] = True
        elif parsed_time:
            result["time"] = parsed_time.strftime("%H:%M")
        if session.last_question == "name" and not result and re.fullmatch(r"[a-z][a-z' -]{1,50}", text):
            result["name"] = (
                text.removeprefix("my name is spelled ").removeprefix("my name is ").removeprefix("name is ").title()
            )
        if session.last_question == "phone" and "phone" not in result:
            digits = re.sub(r"\D", "", text)
            if digits:
                result["phone_fragment"] = digits
        if session.last_question == "vehicle" and "vehicle" not in result and len(text.split()) <= 5:
            result["vehicle"] = text.title()
        return result

    def _merge(self, session: Session, candidates: dict) -> dict:
        accepted: dict = {}
        for key, value in candidates.items():
            if key == "phone_fragment":
                combined = session.draft.get("phone_partial", "") + value
                if len(combined) == 10:
                    session.draft.pop("phone_partial", None)
                    session.draft["phone"] = combined
                    accepted["phone"] = combined
                elif len(combined) < 10:
                    session.draft["phone_partial"] = combined
                    accepted["phone_partial"] = combined
            elif key == "vehicle_year" and 1980 <= value <= self.clock().year + 1:
                session.draft[key] = value
                accepted[key] = value
            elif key in FIELDS and key != "time_ambiguous":
                session.draft[key] = value
                accepted[key] = value
        return accepted

    def _resolve_slot(
        self, session: Session, turn_id: str, before: str | None, candidates: dict, accepted: dict
    ) -> dict:
        if candidates.get("time_ambiguous") and "time" not in session.draft:
            session.last_question = "time"
            return self._commit(
                session,
                turn_id,
                before,
                "clarify_time",
                "missing_meridiem",
                "Did you mean AM or PM?",
                candidates,
                accepted,
            )
        requested = datetime.fromisoformat(f"{session.draft['date']}T{session.draft['time']}").replace(tzinfo=TZ)
        if requested <= self.clock():
            session.draft.pop("date", None)
            session.draft.pop("time", None)
            session.last_question = "date"
            return self._commit(
                session,
                turn_id,
                before,
                "ask_field",
                "past_slot",
                "That time is in the past. What future date works?",
                candidates,
                accepted,
            )
        if self.store.is_available(requested, session.draft["service"]):
            session.draft["slot"] = requested.isoformat()
            session.state, session.last_question, session.expected_answer = (
                State.CONFIRMING,
                "confirm_booking",
                "boolean",
            )
            return self._commit(
                session,
                turn_id,
                before,
                "request_confirmation",
                "slot_available",
                self._summary(session),
                candidates,
                accepted,
            )
        return self._offer_alternatives(session, turn_id, before, "slot_unavailable")

    def _offer_alternatives(self, session: Session, turn_id: str, before: str | None, reason: str) -> dict:
        requested = datetime.fromisoformat(f"{session.draft['date']}T{session.draft['time']}").replace(tzinfo=TZ)
        session.offered_slots = [
            slot.isoformat() for slot in self.store.alternatives(requested, session.draft["service"])
        ]
        session.state, session.last_question = State.CHOOSING_SLOT, "slot_choice"
        choices = "; ".join(f"option {i + 1}: {slot}" for i, slot in enumerate(session.offered_slots))
        return self._commit(
            session, turn_id, before, "offer_alternatives", reason, f"That slot is unavailable. {choices}", {}
        )

    def _summary(self, session: Session) -> str:
        d = session.draft
        service = SERVICES[d["service"]].label
        return (
            f"Please confirm: {service} for a {d['vehicle_year']} {d['vehicle']} "
            f"at {d['slot']}, for {d['name']}. Say yes or no."
        )

    def _commit(
        self,
        session: Session,
        turn_id: str,
        before: str | None,
        action: str,
        reason: str,
        reply: str,
        candidates: dict,
        accepted: dict | None = None,
    ) -> dict:
        session.version += 1
        session.last_activity_at = self.clock()
        response = self._response(session, action, reason, reply, before, candidates, accepted or {})
        session.processed_turns[turn_id] = response
        return response

    @staticmethod
    def _response(
        session: Session,
        action: str,
        reason: str,
        reply: str,
        before: str | None = None,
        candidates: dict | None = None,
        accepted: dict | None = None,
    ) -> dict:
        return {
            "conversation_id": session.conversation_id,
            "version": session.version,
            "status": session.status.value,
            "state_before": before,
            "state": session.state.value if session.state else None,
            "action": action,
            "reason": reason,
            "reply": reply,
            "candidates": candidates or {},
            "accepted": accepted or {},
            "pending_field": session.last_question if session.status == Status.ACTIVE else None,
            "draft": {k: v for k, v in session.draft.items() if k not in {"phone", "phone_partial"}},
            "offered_slots": session.offered_slots,
        }

    @staticmethod
    def _matches(text: str, phrases: tuple[str, ...]) -> bool:
        return any(re.search(rf"\b{re.escape(phrase)}\b", text) for phrase in phrases)

    @staticmethod
    def _parse_date(text: str, today: date) -> date | None:
        if "tomorrow" in text:
            return today + timedelta(days=1)
        iso = re.search(r"\b(20\d\d)-(\d\d)-(\d\d)\b", text)
        if iso:
            return date.fromisoformat(iso.group())
        weekdays = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
        for name, target in weekdays.items():
            if name in text:
                if f"next {name}" in text:
                    days = 7 - today.weekday() + target
                else:
                    days = (target - today.weekday()) % 7 or 7
                return today + timedelta(days=days)
        return None

    @staticmethod
    def _parse_time(text: str) -> time | str | None:
        part = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text)
        if part:
            hour, minute, meridiem = int(part.group(1)), int(part.group(2) or 0), part.group(3)
            if not 1 <= hour <= 12 or minute > 59:
                return None
            hour = hour % 12 + (12 if meridiem == "pm" else 0)
            return time(hour, minute)
        if "morning" in text:
            return time(9)
        if "afternoon" in text:
            return time(14)
        if re.search(r"\bat \d{1,2}\b", text):
            return "ambiguous"
        return None


class StaleTurnError(Exception):
    pass


class SessionExpiredError(Exception):
    pass


class SessionTerminalError(Exception):
    pass
