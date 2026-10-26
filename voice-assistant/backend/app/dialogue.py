"""Deterministic clinic appointment dialogue state machine."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Callable, Optional

from . import config as C
from .db import Database, SlotChanged
from .email_service import EmailService
from .nlu import Parsed, parse


def fmt_time(minutes: int) -> str:
    hour, minute = divmod(minutes, 60)
    return f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"


def fmt_date(value: str) -> str:
    day = date.fromisoformat(value)
    return f"{day.strftime('%A, %B')} {day.day}, {day.year}"


PROMPTS = {
    "guardian_name": "What is the parent or guardian's name?",
    "child_name": "What is the child's name?",
    "child_age": "How old is the child?",
    "date": "What weekday appointment date would you like?",
    "token": "Please tell me the appointment date and token number.",
    "verification": "Please provide the verified email address and its one-time code.",
    "new_date": "What weekday would you like to reschedule to?",
}


@dataclass
class Call:
    session_id: str
    state: str = "IDLE"
    task: Optional[str] = None
    slots: dict = field(default_factory=lambda: {
        "guardian_name": None, "child_name": None, "child_age": None,
        "date": None, "contact": None, "email": None, "token": None,
    })
    email_verified: bool = False
    expecting: Optional[str] = None
    prompt: str = ""
    turn: int = 0
    fails: int = 0
    outcome: Optional[str] = None
    appointment: Optional[dict] = None
    last_reply: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(value: str) -> "Call":
        return Call(**json.loads(value))


@dataclass
class Result:
    reply: str
    intent: str
    extracted: dict
    action: str
    state: str
    expecting: Optional[str]
    slots: dict
    end: bool
    trace: list
    appointment: Optional[dict] = None


class Brain:
    def __init__(self, db: Database, now: Optional[Callable[[], datetime]] = None,
                 email_service: Optional[EmailService] = None):
        self.db = db
        self.now = now or datetime.now
        self.email_service = email_service or EmailService(db)
        self.trace: list[str] = []
        self.action = "NOOP"

    @property
    def today(self) -> date:
        return self.now().date()

    def log(self, message: str):
        self.trace.append(message)

    def start(self, call: Call) -> str:
        call.prompt = "I can book, check, cancel, or reschedule a children's specialist appointment. How can I help?"
        call.last_reply = f"Thank you for calling {C.CLINIC_NAME}. {call.prompt}"
        return call.last_reply

    def handle(self, call: Call, text: str) -> Result:
        call.turn += 1
        self.trace, self.action = [], "NOOP"
        parsed = parse(text, self.today)
        self.log(f"state={call.state} intent={parsed.intent}")
        if call.state == "ENDED":
            reply, self.action = "This call has ended. Please start a new call.", "ENDED"
        elif parsed.empty:
            reply = self._fail(call, "I didn't hear anything.")
        elif parsed.intent == "GOODBYE":
            call.state, call.outcome, self.action = "ENDED", "caller_hung_up", "END_CALL"
            reply = "Thank you for calling the clinic. Goodbye."
        elif parsed.intent == "HELP" or parsed.intent == "GREETING":
            reply = self.start(call)
            self.action = "MENU"
        elif call.state == "IDLE":
            reply = self._idle(call, parsed)
        elif call.state == "COLLECT_BOOK":
            reply = self._collect_booking(call, parsed)
        elif call.state == "CONFIRM_BOOK":
            reply = self._confirm_booking(call, parsed)
        elif call.state == "COLLECT_LOOKUP":
            reply = self._collect_lookup(call, parsed)
        elif call.state == "CONFIRM_CANCEL":
            reply = self._confirm_cancel(call, parsed)
        elif call.state == "COLLECT_RESCHEDULE":
            reply = self._collect_reschedule(call, parsed)
        elif call.state == "CONFIRM_RESCHEDULE":
            reply = self._confirm_reschedule(call, parsed)
        elif call.state in ("VERIFY_BOOK_EMAIL", "VERIFY_LOOKUP_EMAIL"):
            reply = self._verify_email(call, parsed)
        else:
            reply = self._fail(call, "I couldn't understand that.")
        call.last_reply = reply
        return Result(reply, parsed.intent, parsed.summary(), self.action, call.state,
                      call.expecting, dict(call.slots), call.state == "ENDED", list(self.trace),
                      self._public_appointment(call.appointment)
                      if self.action.startswith(("BOOKED:", "CANCELLED:", "RESCHEDULED:"))
                      or self.action in ("APPOINTMENT_FOUND", "CONFIRM_CANCEL") else None)

    @staticmethod
    def _public_appointment(appointment: Optional[dict]) -> Optional[dict]:
        if not appointment:
            return None
        return {key: appointment[key] for key in (
            "token", "appointment_date", "start_min", "end_min", "status"
        ) if key in appointment}

    def _fail(self, call: Call, prefix: str) -> str:
        call.fails += 1
        self.log(f"misunderstanding #{call.fails}")
        if call.fails >= C.MAX_FAILS:
            call.state, call.outcome, self.action = "ENDED", "escalated", "ESCALATE_HUMAN"
            return "I'm having trouble understanding. Please contact the clinic team for help."
        self.action = "REPROMPT"
        return f"{prefix} {call.prompt}".strip()

    def _idle(self, call: Call, parsed: Parsed) -> str:
        call.fails = 0
        if parsed.intent == "BOOK":
            call.task, call.state = "book", "COLLECT_BOOK"
            call.slots = {"guardian_name": None, "child_name": None, "child_age": None, "date": None,
                          "contact": None, "email": None, "token": None}
            call.email_verified = False
            self._apply_details(call, parsed)
            return self._advance_booking(call)
        if parsed.intent in ("CHECK", "CANCEL", "RESCHEDULE"):
            call.task = {"CHECK": "check", "CANCEL": "cancel", "RESCHEDULE": "reschedule"}[parsed.intent]
            call.slots = {"guardian_name": None, "child_name": None, "child_age": None,
                          "date": None, "contact": None, "email": None, "token": None}
            call.email_verified = False
            call.state = "COLLECT_LOOKUP"
            self._apply_lookup(call, parsed)
            return self._lookup_prompt(call)
        call.prompt = "You can book, check, cancel, or reschedule an appointment. What would you like to do?"
        self.action = "MENU"
        return call.prompt

    def _apply_details(self, call: Call, parsed: Parsed):
        for key in ("guardian_name", "child_name", "child_age", "contact"):
            value = getattr(parsed, key)
            if value is not None:
                if key == "child_age" and not 0 <= value <= 18:
                    self.log("rejected invalid child age")
                    continue
                call.slots[key] = value
                self.log(f"slot {key} captured")
        if parsed.email and self.db.valid_email(parsed.email):
            call.slots["email"] = parsed.email
            call.email_verified = False
            self.log("email address captured; not verified")
        if parsed.date_error:
            self.log("rejected invalid appointment date")
        elif parsed.date:
            call.slots["date"] = parsed.date.isoformat()
            self.log("appointment date captured")
        if call.expecting and call.expecting in ("guardian_name", "child_name") and not getattr(parsed, call.expecting):
            value = re.sub(r"[^A-Za-z' -]", "", parsed.norm).strip()
            if value and len(value.split()) <= 3 and not re.search(r"\b(book|appointment|age|child|guardian|parent|tomorrow|today|monday|tuesday|wednesday|thursday|friday)\b", value, re.I):
                call.slots[call.expecting] = value.title()
                self.log(f"slot {call.expecting} captured")
        if call.expecting == "child_age" and parsed.child_age is None:
            match = re.fullmatch(r"\s*(\d{1,2})\s*(?:years?|months?)?\s*(?:old)?\s*", parsed.norm)
            if match:
                age = int(match.group(1))
                if 0 <= age <= 18:
                    call.slots["child_age"] = age
                    self.log("child age captured")
                else:
                    self.log("rejected invalid child age")
        if call.expecting == "date" and not parsed.date and not parsed.date_error:
            parsed_date, error = self._context_date(parsed.norm)
            if parsed_date:
                call.slots["date"] = parsed_date.isoformat()
                self.log("appointment date captured")
            elif error:
                self.log("rejected invalid appointment date")

    def _context_date(self, text: str):
        from .nlu import extract_date
        return extract_date(text, self.today)

    def _advance_booking(self, call: Call) -> str:
        for key in ("guardian_name", "child_name", "child_age", "date"):
            value = call.slots[key]
            if value is None:
                call.state, call.expecting = "COLLECT_BOOK", key
                call.prompt = PROMPTS[key]
                self.action = f"ASK:{key}"
                return call.prompt
        try:
            day = date.fromisoformat(call.slots["date"])
            if day < self.today:
                call.slots["date"] = None
                call.expecting = "date"
                call.prompt = "That date has passed. " + PROMPTS["date"]
                self.action = "REJECT:past_date"
                return call.prompt
            if not C.is_working_day(day):
                call.slots["date"] = None
                call.expecting = "date"
                call.prompt = "The clinic is open Monday through Friday only. " + PROMPTS["date"]
                self.action = "REJECT:closed_day"
                return call.prompt
            preview = self.db.preview(day.isoformat())
        except ValueError as error:
            call.slots["date"] = None
            call.expecting = "date"
            call.prompt = f"{error} {PROMPTS['date']}"
            self.action = "REJECT:date"
            return call.prompt
        if preview is None:
            if day == self.today and self.db.schedule(day.isoformat())["active_count"] < C.DAILY_CAPACITY:
                message = "No appointment times remain today. Please choose another weekday."
            else:
                message = "All 35 appointment tokens are booked for that weekday. Please choose another date."
            call.expecting, call.prompt = "date", message
            self.action = "UNAVAILABLE"
            return call.prompt
        call.slots["token"] = preview["token"]
        call.slots["time"] = preview["start_min"]
        if not call.slots.get("email"):
            call.state, call.expecting = "COLLECT_BOOK", "email"
            call.prompt = "What email address should receive the appointment notification?"
            self.action = "ASK:email"
            return call.prompt
        if not call.email_verified:
            return self._send_verification(call, "booking")
        call.state, call.expecting = "CONFIRM_BOOK", "yesno"
        call.prompt = (f"Your appointment is available for Token Number {preview['token']} on "
                       f"{day.strftime('%A, %B')} {day.day} at {fmt_time(preview['start_min'])}. "
                       "Would you like me to confirm it?")
        self.action = "OFFER_APPOINTMENT"
        self.log("available appointment token selected")
        return call.prompt

    def _collect_booking(self, call: Call, parsed: Parsed) -> str:
        if parsed.intent == "CANCEL" and not parsed.date and parsed.token is None:
            call.state, call.task = "IDLE", None
            call.prompt = "Okay, I haven't booked anything. How else can I help?"
            self.action = "ABANDON_BOOKING"
            return call.prompt
        self._apply_details(call, parsed)
        if call.expecting == "email" and parsed.email:
            if not self.db.valid_email(parsed.email):
                return self._fail(call, "Please provide a valid email address.")
            return self._send_verification(call, "booking")
        if call.expecting == "email":
            return self._fail(call, "Please provide a valid email address.")
        call.fails = 0
        return self._advance_booking(call)

    def _confirm_booking(self, call: Call, parsed: Parsed) -> str:
        if parsed.no:
            call.state, call.task, call.expecting = "IDLE", None, None
            call.prompt = "Okay, I haven't booked the appointment. How else can I help?"
            self.action = "BOOKING_DECLINED"
            return call.prompt
        if not parsed.yes:
            call.prompt = "Please say yes to confirm or no to decline. " + call.prompt
            return self._fail(call, "")
        try:
            preview = self.db.preview(call.slots["date"])
            if preview is None:
                call.state, call.expecting = "COLLECT_BOOK", "date"
                call.slots["token"] = call.slots["time"] = None
                self.action = "UNAVAILABLE"
                active = self.db.schedule(call.slots["date"])["active_count"]
                if date.fromisoformat(call.slots["date"]) == self.today and active < C.DAILY_CAPACITY:
                    return "No appointment times remain today. Please choose another weekday."
                return "All 35 appointment tokens are now booked. Please choose another date."
            if preview["token"] != call.slots["token"]:
                call.state = "COLLECT_BOOK"
                call.slots["token"], call.slots["time"] = preview["token"], preview["start_min"]
                return self._advance_booking(call)
            appointment = self.db.create_appointment(
                call.slots["date"], call.slots, expected_token=call.slots["token"]
            )
        except SlotChanged:
            call.state = "COLLECT_BOOK"
            return self._advance_booking(call)
        except ValueError as error:
            call.state, call.expecting = "COLLECT_BOOK", "date"
            call.slots["date"] = None
            self.action = "REJECT:date"
            return f"{error} {PROMPTS['date']}"
        if appointment is None:
            call.state, call.expecting = "COLLECT_BOOK", "date"
            call.slots["token"] = call.slots["time"] = None
            self.action = "UNAVAILABLE"
            return "That token was just taken and no appointment was saved. Please choose another weekday."
        call.appointment = appointment
        call.state, call.task, call.expecting, call.outcome = "IDLE", None, None, "booked"
        self.action = f"BOOKED:{appointment['token']}"
        self.log("appointment transaction committed")
        call.appointment = self._public_appointment(appointment)
        self._clear_patient_slots(call)
        self.email_service.send_pending_notifications()
        if self.db.notification_status(appointment["id"], "booked") != "sent":
            return (f"Your appointment is confirmed for Token Number {appointment['token']} on "
                    f"{fmt_date(appointment['appointment_date'])} at {fmt_time(appointment['start_min'])}. "
                    "The email could not be delivered yet; the clinic will retry it.")
        return (f"Your appointment is confirmed for Token Number {appointment['token']} on "
                f"{fmt_date(appointment['appointment_date'])} at {fmt_time(appointment['start_min'])}. "
                "A confidential confirmation was sent to your verified email.")

    def _apply_lookup(self, call: Call, parsed: Parsed):
        if parsed.date:
            call.slots["date"] = parsed.date.isoformat()
        if parsed.token is not None:
            call.slots["token"] = parsed.token
        if parsed.email and self.db.valid_email(parsed.email):
            call.slots["email"] = parsed.email
            call.email_verified = False
        elif parsed.email:
            call.slots["email"] = None
            call.email_verified = False

    def _lookup_prompt(self, call: Call) -> str:
        if call.slots["token"] is None or call.slots["date"] is None:
            call.prompt, call.expecting = PROMPTS["token"], "token"
        elif not call.slots["email"]:
            call.prompt, call.expecting = "What is the email address associated with this appointment?", "email"
        elif not call.email_verified:
            return self._send_verification(call, "lookup")
        else:
            return self._resolve_lookup(call)
        self.action = f"ASK:{call.expecting}"
        return call.prompt

    def _collect_lookup(self, call: Call, parsed: Parsed) -> str:
        self._apply_lookup(call, parsed)
        if parsed.email and not self.db.valid_email(parsed.email):
            return "I cannot disclose another patient's private appointment information."
        return self._lookup_prompt(call)

    def _resolve_lookup(self, call: Call) -> str:
        try:
            appointment = self.db.find_appointment(
                call.slots["date"], call.slots["token"], call.slots["email"]
            )
        except ValueError as error:
            call.slots["date"] = None
            call.expecting, call.prompt = "token", f"{error} {PROMPTS['token']}"
            return call.prompt
        if not appointment:
            call.state, call.task, call.expecting = "IDLE", None, None
            self.action = "NOT_FOUND"
            return "I cannot disclose another patient's private appointment information."
        call.appointment = self._public_appointment(appointment)
        if call.task == "check":
            call.state, call.task, call.expecting, self.action = "IDLE", None, None, "APPOINTMENT_FOUND"
            self._clear_patient_slots(call)
            return (f"Appointment verified: Token Number {appointment['token']} on "
                    f"{fmt_date(appointment['appointment_date'])} at {fmt_time(appointment['start_min'])}. Status: active.")
        if call.task == "cancel":
            call.state, call.expecting = "CONFIRM_CANCEL", "yesno"
            call.prompt = (f"I found Token Number {appointment['token']} on "
                           f"{fmt_date(appointment['appointment_date'])} at {fmt_time(appointment['start_min'])}. "
                           "Do you want me to cancel it?")
            self.action = "CONFIRM_CANCEL"
            return call.prompt
        call.state, call.expecting, call.task = "COLLECT_RESCHEDULE", "new_date", "reschedule"
        call.prompt = "What weekday would you like to reschedule to?"
        return call.prompt

    def _confirm_cancel(self, call: Call, parsed: Parsed) -> str:
        if parsed.yes:
            if not self.db.cancel_appointment(call.appointment["id"]):
                call.state, call.task = "IDLE", None
                self.action = "NOT_FOUND"
                return "I couldn't cancel that appointment because it is no longer active."
            call.appointment = self._public_appointment(self.db.get_appointment(call.appointment["id"]))
            self.action = f"CANCELLED:{call.appointment['token']}"
            call.state, call.task, call.outcome = "IDLE", None, "cancelled"
            cancelled_appointment = self.db.get_appointment(call.appointment["id"])
            self.email_service.send_pending_notifications()
            self._clear_patient_slots(call)
            if self.db.notification_status(cancelled_appointment["id"], "cancelled") != "sent":
                return "The appointment was cancelled. The email could not be delivered yet; the clinic will retry it."
            return f"Cancelled Token Number {call.appointment['token']}. The appointment record is preserved."
        if parsed.no:
            call.state, call.task, self.action = "IDLE", None, "CANCELLATION_DECLINED"
            return "The appointment remains active. How else can I help?"
        return self._fail(call, "Please say yes to confirm cancellation or no to keep it.")

    def _collect_reschedule(self, call: Call, parsed: Parsed) -> str:
        if parsed.date:
            call.slots["new_date"] = parsed.date.isoformat()
        elif parsed.date_error:
            self.action = "REJECT:date"
            return self._fail(call, "That isn't a valid date.")
        if not call.slots.get("new_date"):
            return self._fail(call, PROMPTS["new_date"])
        try:
            day = date.fromisoformat(call.slots["new_date"])
            if day < self.today:
                raise ValueError("Appointments cannot be rescheduled to a past date.")
            if not C.is_working_day(day):
                raise ValueError("The clinic is open Monday through Friday only.")
            preview = self.db.preview(day.isoformat())
        except ValueError as error:
            call.slots["new_date"] = None
            self.action = "REJECT:date"
            return f"{error} {PROMPTS['new_date']}"
        if not preview:
            call.slots["new_date"] = None
            self.action = "UNAVAILABLE"
            return "All 35 appointment tokens are booked for that weekday. Please choose another date."
        call.slots["new_token"] = preview["token"]
        call.state, call.expecting = "CONFIRM_RESCHEDULE", "yesno"
        call.prompt = (f"Token Number {preview['token']} is available on {fmt_date(day.isoformat())} at "
                       f"{fmt_time(preview['start_min'])}. Should I reschedule the appointment?")
        self.action = "OFFER_RESCHEDULE"
        return call.prompt

    def _confirm_reschedule(self, call: Call, parsed: Parsed) -> str:
        if parsed.no:
            call.state, call.task, self.action = "IDLE", None, "RESCHEDULE_DECLINED"
            return "The original appointment is unchanged."
        if not parsed.yes:
            return self._fail(call, "Please say yes to reschedule or no to keep the original appointment.")
        try:
            preview = self.db.preview(call.slots["new_date"])
            if not preview:
                call.state, call.expecting = "COLLECT_RESCHEDULE", "new_date"
                return "All appointment tokens for that weekday have just been taken. Please choose another day."
            if preview["token"] != call.slots["new_token"]:
                call.state = "COLLECT_RESCHEDULE"
                return self._collect_reschedule(call, Parsed(text="", norm="", date=date.fromisoformat(call.slots["new_date"])))
            appointment = self.db.reschedule_appointment(
                call.appointment["id"], call.slots["new_date"], expected_token=call.slots["new_token"]
            )
        except SlotChanged:
            call.state = "COLLECT_RESCHEDULE"
            new_date = date.fromisoformat(call.slots["new_date"])
            return self._collect_reschedule(call, Parsed(text="", norm="", date=new_date))
        except ValueError as error:
            call.state, call.expecting = "COLLECT_RESCHEDULE", "new_date"
            return f"{error} {PROMPTS['new_date']}"
        if not appointment:
            call.state, call.expecting = "COLLECT_RESCHEDULE", "new_date"
            self.action = "UNAVAILABLE"
            return "That token is no longer available. The original appointment remains active."
        call.appointment = appointment
        call.state, call.task, call.outcome = "IDLE", None, "rescheduled"
        self.action = f"RESCHEDULED:{appointment['token']}"
        call.appointment = self._public_appointment(appointment)
        self._clear_patient_slots(call)
        self.email_service.send_pending_notifications()
        if self.db.notification_status(appointment["id"], "rescheduled") != "sent":
            return "The appointment was rescheduled. The email could not be delivered yet; the clinic will retry it."
        return (f"Rescheduled. Token Number {appointment['token']} is confirmed for "
                f"{fmt_date(appointment['appointment_date'])} at {fmt_time(appointment['start_min'])}.")

    def _send_verification(self, call: Call, purpose: str) -> str:
        email = call.slots.get("email")
        if not self.db.valid_email(email):
            call.state = "COLLECT_BOOK" if purpose == "booking" else "COLLECT_LOOKUP"
            call.expecting = "email"
            call.prompt = "Please provide a valid email address."
            self.action = "REJECT:email"
            return call.prompt
        try:
            sent = self.email_service.send_verification(call.session_id, email, purpose)
        except ValueError:
            sent = False
        if not sent:
            call.state = "COLLECT_BOOK" if purpose == "booking" else "COLLECT_LOOKUP"
            call.expecting = "email"
            call.prompt = "I couldn't send an email verification code. No appointment information was disclosed. Please try another address or contact the clinic."
            self.action = "EMAIL_UNAVAILABLE"
            return call.prompt
        call.state = "VERIFY_BOOK_EMAIL" if purpose == "booking" else "VERIFY_LOOKUP_EMAIL"
        call.expecting = "verification_code"
        call.prompt = "If this email address can be verified, a one-time code has been sent. Please enter the six-digit code."
        self.action = "EMAIL_VERIFICATION_SENT"
        return call.prompt

    def _verify_email(self, call: Call, parsed: Parsed) -> str:
        purpose = "booking" if call.state == "VERIFY_BOOK_EMAIL" else "lookup"
        code = parsed.verification_code
        if not code or not self.email_service.verify_code(
            call.session_id, call.slots.get("email", ""), purpose, code
        ):
            self.action = "EMAIL_VERIFICATION_FAILED"
            return "That verification code is invalid or expired. Please enter the code sent to your email."
        call.email_verified = True
        self.log("email ownership verified")
        if purpose == "booking":
            call.state = "COLLECT_BOOK"
            return self._advance_booking(call)
        call.state = "COLLECT_LOOKUP"
        return self._resolve_lookup(call)

    @staticmethod
    def _clear_patient_slots(call: Call):
        for key in ("guardian_name", "child_name", "child_age", "contact", "email"):
            call.slots[key] = None
        call.email_verified = False
