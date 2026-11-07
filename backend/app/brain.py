"""The brain: a deterministic dialogue state machine with slot filling. No LLM involved."""
from dataclasses import dataclass, field
from datetime import date

from . import nlu
from .schedule import Schedule, fmt, fmt_time

PROMPTS = {
    "LISTEN": "Would you like to book, reschedule or cancel an appointment?",
    "ASK_NAME": "May I have your full name?",
    "ASK_DATE": "What day would you like?",
    "ASK_TIME": "What time works for you?",
    "CONFIRM": "Is that correct? Please say yes or no.",
}


@dataclass
class Session:
    state: str = "START"
    intent: str | None = None
    slots: dict = field(default_factory=dict)
    pending_hour: tuple | None = None
    misses: int = 0
    last_reply: str = ""
    found: tuple | None = None
    done: bool = False


@dataclass
class Turn:
    reply: str
    state: str
    intent: str | None
    slots: dict
    trace: list
    done: bool


class Brain:
    def __init__(self, schedule: Schedule, today: date | None = None):
        self.sched, self.today = schedule, today or date.today()

    # -- helpers -----------------------------------------------------------
    def _say(self, s, reply, tr):
        s.last_reply = reply
        return Turn(reply, s.state, s.intent, dict(s.slots), tr, s.done)

    def _end(self, s, reply, tr):
        s.done, s.state = True, "ENDED"
        return self._say(s, reply, tr)

    def _miss(self, s, tr, why):
        s.misses += 1
        tr.append(f"miss #{s.misses}: {why}")
        if s.misses >= 3:
            return self._end(s, "I'm having trouble understanding. I'll pass you to our front desk. Goodbye.", tr)
        key = s.state if s.state in PROMPTS else "LISTEN"
        return self._say(s, "Sorry, I didn't catch that. " + PROMPTS[key], tr)

    # -- entry points ------------------------------------------------------
    def greet(self, s):
        s.state = "LISTEN"
        return self._say(s, "Hello, welcome to Demo Clinic. I can book, reschedule or cancel an appointment. How can I help?", ["session started"])

    def handle(self, s, text):
        tr, text = [], (text or "").strip()
        if s.done:
            return self._say(s, "This call has ended.", tr)
        if not text:
            return self._miss(s, tr, "empty transcript")
        intent = nlu.detect_intent(text)
        tr.append(f"intent={intent}")
        if intent == "human":
            return self._end(s, "Of course. Transferring you to our front desk. Goodbye.", tr)
        if intent == "goodbye":
            return self._end(s, "Thanks for calling. Goodbye.", tr)
        if intent == "repeat":
            return self._say(s, s.last_reply or PROMPTS["LISTEN"], tr)

        ents = self._extract(s, text, tr)
        if intent in ("book", "cancel", "reschedule") and intent != s.intent:
            if s.intent:
                tr.append(f"intent switch {s.intent}->{intent}")
                s.slots.pop("date", None), s.slots.pop("time", None)
                s.found, s.pending_hour = None, None
            s.intent = intent
        elif s.intent is None and ents:
            s.intent = "book"
            tr.append("entities without intent -> assume book")

        if s.state == "CONFIRM" and intent in ("yes", "no") and not ents:
            s.misses = 0
            return self._confirm(s, intent, tr)
        if s.intent is None:
            if intent == "greeting":
                return self._say(s, "Hello! " + PROMPTS["LISTEN"], tr)
            return self._miss(s, tr, "no intent")
        if not ents and intent not in ("book", "cancel", "reschedule"):
            return self._miss(s, tr, "nothing usable")
        s.misses = 0
        return self._advance(s, tr)

    # -- internals ---------------------------------------------------------
    def _extract(self, s, text, tr):
        ents = {}
        d = nlu.parse_date(text, self.today)
        r = nlu.parse_time(text, s.pending_hour)
        if d:
            ents["date"] = d
        if r and r[0] == "ok":
            ents["time"], s.pending_hour = r[1], None
        elif r:
            s.pending_hour = r[1]
            s.slots.pop("time", None)
            ents["ambiguous"] = True
            tr.append(f"ambiguous time {r[1]}")
        n = nlu.parse_name(text, expecting=s.state == "ASK_NAME" and not d and not r)
        if n:
            ents["name"] = n
        for k in ("date", "time", "name"):
            if k in ents:
                if s.slots.get(k) not in (None, ents[k]):
                    tr.append(f"correction {k}: {s.slots[k]} -> {ents[k]}")
                s.slots[k] = ents[k]
        if ents:
            tr.append("slots " + str({k: v for k, v in ents.items() if k != "ambiguous"}))
        return ents

    def _advance(self, s, tr):
        sl = s.slots
        if "name" not in sl:
            s.state = "ASK_NAME"
            return self._say(s, PROMPTS["ASK_NAME"], tr)
        if s.intent in ("cancel", "reschedule") and not s.found:
            s.found = self.sched.find(sl["name"])
            if not s.found:
                tr.append("lookup failed")
                sl.pop("name")
                s.state = "ASK_NAME"
                return self._say(s, "I couldn't find a booking under that name. Could you repeat your name?", tr)
            tr.append(f"found booking {s.found}")
        if s.intent == "cancel":
            s.state = "CONFIRM"
            return self._say(s, f"I found your appointment on {fmt(*s.found)}. Shall I cancel it?", tr)
        if s.pending_hour:
            h, m = s.pending_hour
            s.state = "ASK_TIME"
            return self._say(s, f"Is {h}:{m:02d} in the morning or in the evening?", tr)
        if "date" not in sl:
            s.state = "ASK_DATE"
            return self._say(s, PROMPTS["ASK_DATE"], tr)
        if "time" not in sl:
            s.state = "ASK_TIME"
            return self._say(s, PROMPTS["ASK_TIME"], tr)

        err = self.sched.check(sl["date"], sl["time"], self.today)
        if err:
            tr.append(f"validation failed: {err}")
            d, t = sl["date"], sl["time"]
            if err in ("past", "weekend"):
                sl.pop("date")
                s.state = "ASK_DATE"
                msg = "That date has already passed." if err == "past" else "We're closed on weekends and open Monday to Friday."
                return self._say(s, f"{msg} What other day works?", tr)
            sl.pop("time")
            s.state = "ASK_TIME"
            alts = ", ".join(fmt_time(a) for a in self.sched.alternatives(d, t))
            msg = ("Sorry, that time is already booked." if err == "taken"
                   else "We book every half hour between 9 AM and 5 PM.")
            return self._say(s, f"{msg} The closest openings are {alts}. Which works?", tr)

        s.state = "CONFIRM"
        new = fmt(sl["date"], sl["time"])
        if s.intent == "reschedule":
            return self._say(s, f"I'll move your appointment from {fmt(*s.found)} to {new}. Is that correct?", tr)
        return self._say(s, f"To confirm: an appointment for {sl['name']} on {new}. Is that correct?", tr)

    def _confirm(self, s, answer, tr):
        sl = s.slots
        if answer == "no":
            if s.intent == "cancel":
                return self._end(s, "Okay, I've left your appointment as it is. Goodbye.", tr)
            sl.pop("date", None), sl.pop("time", None)
            s.state = "ASK_DATE"
            return self._say(s, "No problem. What day and time would you prefer?", tr)
        if s.intent == "cancel":
            self.sched.cancel(s.found)
            return self._end(s, "Your appointment is cancelled. Goodbye.", tr)
        if s.intent == "reschedule":
            self.sched.cancel(s.found)
        ref = self.sched.book(sl["name"], sl["date"], sl["time"])
        tr.append(f"booked {ref}")
        return self._end(s, f"You're all set, {sl['name']}. Booked for {fmt(sl['date'], sl['time'])}. Your reference is {ref}. Goodbye.", tr)
