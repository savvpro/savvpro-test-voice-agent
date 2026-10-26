"""The brain: one phone call, turn by turn.

Each turn: clean the text -> understand it (intent + details) -> update what
we know -> pick ONE next action -> say it. The order of checks below is the
policy; every turn returns a Decision explaining what was heard and why the
assistant did what it did. No language model is involved.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta

from app.clinic.calendar import (
    ADDRESS_TEXT,
    HOURS_TEXT,
    INSURANCE_TEXT,
    SERVICE_LABELS,
    Booking,
    Calendar,
    say_date,
    say_slot,
    say_time,
)
from app.nlu.intents import Understanding, understand, wants_to_skip
from app.nlu.normalize import normalize
from app.nlu.when import find_date, find_part_of_day, find_time

MAX_MISSES = 3
_NOT_A_NAME = {
    "yes", "no", "yeah", "nope", "sure", "ok", "okay", "the", "a", "an", "it", "that", "this", "what",
    "first", "second", "one", "hello", "hi", "hey", "sorry", "wait", "please", "thanks", "um", "uh",
    "hmm", "blah", "why", "who", "huh", "maybe", "dunno", "idk", "nothing", "same", "again",
}
FAQ = {"hours": HOURS_TEXT, "location": ADDRESS_TEXT, "insurance": INSURANCE_TEXT}


@dataclass
class Decision:
    heard: str
    normalized: str
    intent: str | None
    confidence: float
    extracted: dict
    action: str
    reasons: list[str]
    reply: str
    state: dict
    ended: bool


@dataclass
class State:
    task: str | None = None  # book | reschedule | cancel
    service: str | None = None
    day: date | None = None
    at: time | None = None
    part_of_day: str | None = None
    name: str | None = None
    phone: str | None = None
    phone_skipped: bool = False  # the caller chose not to give one
    booking_id: str | None = None  # existing booking (reschedule / cancel)
    offers: list[datetime] = field(default_factory=list)
    awaiting: str | None = None  # what the last question asked for
    misses: int = 0
    ended: bool = False
    result: str | None = None  # booking id or "cancelled"


class Call:
    def __init__(self, calendar: Calendar, now: datetime):
        self.cal = calendar
        self.now = now
        self.s = State()
        self.last_reply = ""
        self.reasons: list[str] = []

    @property
    def today(self) -> date:
        return self.now.date()

    # ------------------------------------------------------------------
    def greet(self) -> str:
        self.last_reply = (
            "Thanks for calling Brightside Dental, this is the automated assistant. "
            "I can book, move or cancel an appointment. How can I help you today?"
        )
        self.s.awaiting = "task"
        return self.last_reply

    def turn(self, heard: str) -> Decision:
        self.reasons = []
        text = normalize(heard)
        u = understand(text)
        extracted = self._extract(text, u)
        if self.s.ended:
            reply, action = "This call has ended. Start a new call to continue.", "ended"
        else:
            reply, action = self._decide(text, u, extracted)
        self.last_reply = reply
        return Decision(
            heard=heard,
            normalized=text,
            intent=u.intent,
            confidence=round(u.confidence, 2),
            extracted={k: v for k, v in extracted.items() if v is not None},
            action=action,
            reasons=self.reasons,
            reply=reply,
            state=self.snapshot(),
            ended=self.s.ended,
        )

    def snapshot(self) -> dict:
        d = asdict(self.s)
        d["day"] = self.s.day.isoformat() if self.s.day else None
        d["at"] = say_time(self.s.at) if self.s.at else None
        d["offers"] = [say_slot(o, self.today) for o in self.s.offers]
        return d

    # ------------------------------------------------------------------
    def _extract(self, text: str, u: Understanding) -> dict:
        when_time = find_time(text)
        return {
            "date": find_date(text, self.today),
            "time": when_time,
            "part_of_day": find_part_of_day(text),
            "service": u.service,
            "name": u.name or (self._bare_name(text) if self.s.awaiting in ("name", "lookup") else None),
            "phone": u.phone,
            "choice": u.choice,
        }

    def _bare_name(self, text: str) -> str | None:
        # When we just asked for a name, "jane doe" alone is the answer.
        words = text.split()
        if 1 <= len(words) <= 3 and all(w.isalpha() and w not in _NOT_A_NAME for w in words):
            return " ".join(w.capitalize() for w in words)
        return None

    def _note(self, reason: str) -> None:
        self.reasons.append(reason)

    # ------------------------------------------------------------------
    def _decide(self, text: str, u: Understanding, x: dict) -> tuple[str, str]:
        s = self.s
        if not text:
            return self._miss("I didn't catch anything. " + self._question(), "no_input")

        # A phone number is optional for a new booking: "skip", "no", "rather not".
        if s.awaiting == "phone" and s.task == "book" and not x["phone"] and wants_to_skip(text):
            s.phone_skipped = True
            s.misses = 0
            self._note("Caller chose not to give a phone number (it's optional)")
            return self._next_step()

        # 1. Requests that apply at any point in the call.
        if u.intent == "repeat":
            self._note("Caller asked to repeat")
            return self.last_reply, "repeat"
        if u.intent == "restart":
            self.s = State(awaiting="task")
            self._note("Caller asked to start over: all details cleared")
            return "No problem, let's start over. Would you like to book, move or cancel an appointment?", "restart"
        if u.intent == "human":
            return self._end("I'll transfer you to our front desk now. Please hold.", "transfer", "Caller asked for a person")
        if u.intent in FAQ and not (x["date"] or x["time"] or x["phone"]):
            self._note(f"Answered a question about {u.intent}, then returned to the open question")
            follow = self._question() if s.task else "Is there anything I can help you book?"
            return f"{FAQ[u.intent]} {follow}", f"answer_{u.intent}"
        if u.intent == "goodbye" and s.awaiting not in ("confirm",):
            return self._end("Thanks for calling Brightside Dental. Have a great day!", "goodbye", "Caller ended the call")

        # 2. What is this call about?
        if u.intent == "emergency" and s.task in (None, "book"):
            s.task, s.service = "book", "emergency"
            self._note("Emergency words: booking the earliest available visit")
            if not s.day:
                return self._offer(self.cal.earliest(self.now), urgent=True)
        progressed = False
        if u.intent in ("book", "reschedule", "cancel_appointment") and s.awaiting in (None, "task") or (
            u.intent in ("reschedule", "cancel_appointment") and s.task == "book" and not s.result
        ):
            new = {"book": "book", "reschedule": "reschedule", "cancel_appointment": "cancel"}[u.intent]
            if new != s.task:
                self._note(f"Task set to {new} (intent '{u.intent}', confidence {u.confidence:.2f})")
                s.task = new
                progressed = True
        if s.task is None and (x["date"] or x["time"] or x["service"]):
            s.task = "book"
            self._note("No task said, but a date/time/service was given: assuming a new booking")

        # 3. Answers to a pending yes/no.
        if s.awaiting == "confirm":
            if u.intent == "affirm" and not u.correction:
                return self._execute()
            if u.intent == "deny" or u.correction or self._has_new_details(x):
                progressed = self._merge(x, overwrite=True)
                if not progressed:
                    s.awaiting = "what_to_change"
                    self._note("Caller said no without a new detail")
                    return "Sorry about that. What would you like to change: the day, the time, or the type of visit?", "ask_change"
            else:
                return self._miss("Sorry, should I go ahead? Please say yes or no.", "reconfirm")
        elif s.awaiting == "offer":
            pick = self._pick_offer(u, x)
            if pick:
                s.day, s.at = pick.date(), pick.time()
                s.offers = []
                self._note(f"Caller picked {say_slot(pick, self.today)}")
                progressed = True
            elif u.intent == "deny" and not self._has_new_details(x):
                s.offers, s.at = [], None
                s.awaiting = "time"
                return "Okay. What day and time would suit you better?", "ask_time"
            else:
                progressed = self._merge(x, overwrite=True)
        else:
            progressed = self._merge(x, overwrite=u.correction or s.awaiting == "what_to_change") or progressed

        if s.task is None:
            if u.intent is None:
                return self._miss("Sorry, I didn't get that. Would you like to book, move or cancel an appointment?", "ask_task")
            return "Would you like to book, move or cancel an appointment?", "ask_task"

        # Nothing usable in this turn: ask the same question again.
        if not progressed and s.awaiting not in (None, "task"):
            return self._miss(f"Sorry, I didn't get that. {self._question()}", "reask")

        # 4. Fill the next missing detail for this task.
        s.misses = 0
        return self._next_step()

    # ------------------------------------------------------------------
    def _has_new_details(self, x: dict) -> bool:
        return any(x[k] for k in ("date", "time", "service", "part_of_day"))

    def _merge(self, x: dict, overwrite: bool) -> bool:
        s, changed = self.s, False

        def put(attr: str, value, label: str) -> None:
            nonlocal changed
            if value is None:
                return
            old = getattr(s, attr)
            if old is None or overwrite or s.awaiting == {"day": "date", "at": "time"}.get(attr, attr):
                if old != value:
                    if old is not None:
                        self._note(f"Caller changed {label}: {self._fmt(old)} -> {self._fmt(value)}")
                    else:
                        self._note(f"Heard {label}: {self._fmt(value)}")
                    setattr(s, attr, value)
                    changed = True
            elif old != value:
                self._note(f"Ignored {label} {self._fmt(value)} (already have {self._fmt(old)}; say 'actually' to change it)")

        put("service", x["service"], "visit type")
        put("day", x["date"], "day")
        if x["time"]:
            put("at", self._resolve_meridiem(x["time"]), "time")
        if x["part_of_day"] and not x["time"]:
            put("part_of_day", x["part_of_day"], "part of day")
        if x["name"] and (s.awaiting == "name" or s.name is None):
            put("name", x["name"], "name")
        if x["phone"]:
            put("phone", x["phone"], "phone")
        if changed and (x["date"] or x["time"]):
            s.offers = []
        return changed

    def _resolve_meridiem(self, mention) -> time:
        t = mention.value
        if not mention.explicit_meridiem and 1 <= t.hour <= 7:
            self._note(f"'{t.hour}' without AM/PM: read as {t.hour} PM (clinic hours)")
            return time(t.hour + 12, t.minute)
        return t

    def _fmt(self, v) -> str:
        if isinstance(v, date):
            return say_date(v, self.today)
        if isinstance(v, time):
            return say_time(v)
        return str(v)

    # ------------------------------------------------------------------
    def _next_step(self) -> tuple[str, str]:
        s = self.s
        if s.task in ("reschedule", "cancel") and not s.booking_id:
            if not s.phone and not s.name:
                s.awaiting = "lookup"
                return "Sure. What's the name or the phone number the appointment is under?", "ask_lookup"
            booking = (s.phone and self.cal.find_by_phone(s.phone)) or (s.name and self.cal.find_by_name(s.name))
            if not booking:
                s.phone = s.name = None
                s.awaiting = "lookup"
                return self._miss(
                    "I couldn't find an appointment under that. Could you say the full name or the phone number again?",
                    "booking_not_found",
                )
            s.booking_id, s.name, s.service = booking.id, booking.name, booking.service
            self._note(f"Found booking {booking.id} for {booking.name}")
            if s.task == "cancel":
                s.awaiting = "confirm"
                return (
                    f"I found your {SERVICE_LABELS[booking.service]} {self._on(booking.start)}, {booking.name}. "
                    "Do you want me to cancel it?"
                ), "confirm_cancel"
            if not s.day:
                s.awaiting = "date"
                return (
                    f"I found your {SERVICE_LABELS[booking.service]} {self._on(booking.start)}. "
                    "What day would you like to move it to?"
                ), "ask_date"

        if s.task == "book" and not s.service:
            s.awaiting = "service"
            return "What kind of visit do you need: a cleaning, a check-up, a filling, whitening, or a consultation?", "ask_service"

        if not s.day:
            s.awaiting = "date"
            return "What day would you like to come in?", "ask_date"
        problem = self._check_day(s.day)
        if problem:
            s.day = None
            s.awaiting = "date"
            return problem, "invalid_date"

        if not s.at:
            if s.part_of_day:
                return self._offer(self._part_of_day_slots(s.day, s.part_of_day))
            s.awaiting = "time"
            return f"What time on {say_date(s.day, self.today)} works for you?", "ask_time"

        wanted = datetime.combine(s.day, s.at)
        if wanted <= self.now:
            s.at = None
            s.awaiting = "time"
            return "That time has already passed. What later time works for you?", "invalid_time"
        if not self.cal.within_hours(wanted):
            s.at = None
            return self._offer(
                self.cal.alternatives(wanted, self.now),
                lead=f"We're not open at {say_time(wanted)} on {say_date(wanted.date(), self.today)}.",
            )
        if not self.cal.is_free(wanted) and not self._is_own_slot(wanted):
            s.at = None
            return self._offer(
                self.cal.alternatives(wanted, self.now),
                lead=f"{self._first_upper(say_slot(wanted, self.today))} is already taken.",
            )

        if s.task == "book":
            if not s.name:
                s.awaiting = "name"
                return "Great, that time is free. What's your full name?", "ask_name"
            if not s.phone and not s.phone_skipped:
                s.awaiting = "phone"
                return (
                    f"Thanks, {s.name.split()[0]}. What's a phone number to reach you? "
                    "It's optional, so you can say skip."
                ), "ask_phone"

        s.awaiting = "confirm"
        what = SERVICE_LABELS.get(s.service or "", "appointment")
        if s.task == "reschedule":
            return f"To confirm: move your {what} to {say_slot(wanted, self.today)}. Shall I go ahead?", "confirm"
        text_note = f", and we'll text the number ending in {s.phone[-4:]}" if s.phone else ""
        return f"To confirm: {self._a(what)} for {s.name} {self._on(wanted)}{text_note}. Shall I book it?", "confirm"

    def _check_day(self, day: date) -> str | None:
        if day < self.today:
            return "That date has already passed. What day would you like?"
        if day > self.today + timedelta(days=90):
            return "We book up to three months ahead. Could you pick a date before then?"
        if not self.cal.is_open_day(day):
            return f"Sorry, we're closed on {day.strftime('%A')}s. We're open Monday to Saturday. What other day works?"
        if not [t for t in self.cal.free_slots(day) if t > self.now]:
            return f"We're fully booked on {say_date(day, self.today)}. Is there another day that works?"
        return None

    def _part_of_day_slots(self, day: date, part: str) -> list[datetime]:
        bounds = {"morning": (time(0), time(12)), "afternoon": (time(12), time(17)), "evening": (time(15), time(23))}[part]
        free = [t for t in self.cal.free_slots(day) if t > self.now and bounds[0] <= t.time() < bounds[1]]
        return free[:2] or self.cal.alternatives(datetime.combine(day, bounds[0]), self.now)

    def _is_own_slot(self, wanted: datetime) -> bool:
        b = self.cal.bookings.get(self.s.booking_id or "")
        return bool(b and b.start == wanted)

    def _offer(self, slots: list[datetime], lead: str = "", urgent: bool = False) -> tuple[str, str]:
        s = self.s
        if not slots:
            s.awaiting = "date"
            return f"{lead} I don't see anything free soon. Could you try another day?".strip(), "no_availability"
        s.offers, s.awaiting = slots, "offer"
        said = " or ".join(say_slot(o, self.today) for o in slots)
        if urgent:
            lead = "I'm sorry you're in pain. If it's severe swelling or trouble breathing, please call 911. The earliest emergency visit I have is"
            return f"{lead} {said}. Would one of those work?", "offer_urgent"
        self._note(f"Offered {said}")
        return f"{lead} I can offer {said}. Would one of those work?".strip(), "offer_alternatives"

    def _pick_offer(self, u: Understanding, x: dict) -> datetime | None:
        offers = self.s.offers
        if not offers:
            return None
        if u.choice and u.choice <= len(offers):
            return offers[u.choice - 1]
        if x["time"]:
            t = self._resolve_meridiem(x["time"])
            for o in offers:
                if o.time() == t and (not x["date"] or o.date() == x["date"]):
                    return o
        if x["date"] and not x["time"]:
            same = [o for o in offers if o.date() == x["date"]]
            if len(same) == 1:
                return same[0]
        if u.intent == "affirm" and len(offers) == 1:
            return offers[0]
        if u.intent == "affirm" and len(offers) > 1:
            self._note("'Yes' to two options: asking which one")
        return None

    def _execute(self) -> tuple[str, str]:
        s = self.s
        if s.task == "cancel":
            booking = self.cal.bookings[s.booking_id]
            self.cal.cancel(booking.id)
            s.result = "cancelled"
            return self._end(
                f"Done. Your appointment {self._on(booking.start)} is cancelled. Thanks for letting us know. Goodbye!",
                "cancelled",
                f"Cancelled {booking.id}",
            )
        start = datetime.combine(s.day, s.at)
        if not self.cal.is_free(start) and not self._is_own_slot(start):
            s.at = None
            s.awaiting = None
            return self._offer(self.cal.alternatives(start, self.now), lead="Sorry, that slot was just taken.")
        if s.task == "reschedule":
            booking: Booking = self.cal.move(s.booking_id, start)
            verb = "moved"
        else:
            booking = self.cal.add(s.name, s.phone or "", s.service or "checkup", start)
            verb = "booked"
        s.result = booking.id
        return self._end(
            f"You're all set. Your {SERVICE_LABELS[booking.service]} is {verb} {f"to {say_slot(start, self.today)}" if verb == "moved" else self._on(start)}. "
            f"Your confirmation number is {booking.id}. See you then, goodbye!",
            verb,
            f"{verb.capitalize()} {booking.id}",
        )

    # ------------------------------------------------------------------
    def _question(self) -> str:
        return {
            "task": "Would you like to book, move or cancel an appointment?",
            "service": "What kind of visit do you need?",
            "date": "What day would you like to come in?",
            "time": "What time works for you?",
            "name": "What's your full name?",
            "phone": "What's a phone number to reach you? You can also say skip.",
            "lookup": "What's the name or phone number the appointment is under?",
            "offer": "Would one of those times work?",
            "confirm": "Shall I go ahead?",
            "what_to_change": "What would you like to change?",
        }.get(self.s.awaiting or "task", "How can I help?")

    def _miss(self, reply: str, action: str) -> tuple[str, str]:
        self.s.misses += 1
        self._note(f"Did not understand ({self.s.misses}/{MAX_MISSES})")
        if self.s.misses >= MAX_MISSES:
            return self._end(
                "I'm having trouble understanding. Let me transfer you to our front desk. Please hold.",
                "transfer",
                "Too many turns not understood",
            )
        return reply, action

    def _end(self, reply: str, action: str, reason: str) -> tuple[str, str]:
        self.s.ended = True
        self.s.awaiting = None
        self._note(reason)
        return reply, action

    def _on(self, slot: datetime) -> str:
        said = say_slot(slot, self.today)
        return said if said.startswith(("today", "tomorrow")) else f"on {said}"

    @staticmethod
    def _first_upper(text: str) -> str:
        return text[:1].upper() + text[1:]

    @staticmethod
    def _a(noun: str) -> str:
        return f"an {noun}" if noun[0] in "aeiou" else f"a {noun}"

