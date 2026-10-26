"""The 'brain': a rule-based dialogue manager for a dental-clinic phone assistant.

Every decision is made by code in this file and in nlu.py / scheduler.py.
No large AI model is called. Each turn also produces a human-readable `trace`
explaining which rule fired, so the frontend can show what the assistant decided.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Callable

from . import nlu
from .scheduler import HOURS_TEXT, Appointment, Schedule

CLINIC = "Bright Smile Dental"
MAX_FAILURES = 3
BOOKING_WINDOW_DAYS = 60
SERVICE_LIST = "a checkup, cleaning, filling, whitening or extraction"


@dataclass
class Session:
    id: str
    state: str = "start"          # start | collecting | offering | confirming | done | ended
    intent: str | None = None     # book | cancel | reschedule
    slots: dict = field(default_factory=dict)
    period: str | None = None
    awaiting: str | None = None
    question: str = "I can book, change or cancel an appointment. What would you like to do?"
    failures: int = 0
    lookup_failures: int = 0     # consecutive 'appointment not found' answers
    last_reply: str = ""
    alternatives: list = field(default_factory=list)   # [(date, time)]
    target: Appointment | None = None
    ended: bool = False


@dataclass
class TurnResult:
    reply: str
    state: str
    intent: str | None
    slots: dict
    trace: list[str]
    ended: bool
    alternatives: list[str]


# ------------------------------------------------------------ speech helpers
def say_time(t: time) -> str:
    h = t.hour % 12 or 12
    suffix = "AM" if t.hour < 12 else "PM"
    return f"{h} {suffix}" if t.minute == 0 else f"{h}:{t.minute:02d} {suffix}"


def say_day(d: date) -> str:
    return f"{d:%A}, {d:%B} {d.day}"


def say_list(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " or " + items[-1]


def article(service: str) -> str:
    return "an" if service[0] in "aeiou" else "a"


class Brain:
    def __init__(self, schedule: Schedule | None = None,
                 clock: Callable[[], datetime] = datetime.now) -> None:
        self.schedule = schedule or Schedule()
        self.clock = clock

    # ------------------------------------------------------------ public API
    def greeting(self) -> str:
        return (f"Hello, and thank you for calling {CLINIC}. "
                "I can book, change or cancel an appointment. How can I help you today?")

    def new_session(self, session_id: str) -> Session:
        s = Session(id=session_id)
        s.last_reply = self.greeting()
        return s

    def handle(self, s: Session, text: str) -> TurnResult:
        trace: list[str] = []
        if s.ended:
            return self._result(s, "This call has ended. Please start a new call.", trace)

        now = self.clock()
        t = nlu.normalize(text)
        ent = nlu.extract(t, now.date(), awaiting=s.awaiting)
        intent = nlu.detect_intent(t)
        trace.append(f'Heard: "{t}"')
        trace.append(f"Understood: intent={intent or 'none'}; {ent.describe()}")

        reply = self._route(s, t, ent, intent, trace)
        s.last_reply = reply
        return self._result(s, reply, trace)

    # ------------------------------------------------------------ routing
    def _route(self, s: Session, t: str, ent: nlu.Entities, intent: str | None, trace: list[str]) -> str:
        if not t:
            return self._misunderstood(s, trace, "empty input")
        if ent.emergency:
            trace.append("Rule: emergency keyword -> escalate to on-call dentist, end call")
            return self._end(s, "That sounds urgent. I'm transferring you to our on-call dentist right now. "
                                "If you cannot breathe or swallow, please hang up and call emergency services.")
        if intent == "human":
            trace.append("Rule: caller asked for a person -> hand off, end call")
            return self._end(s, "Of course. I'm transferring you to our receptionist now. Please hold.")
        if intent == "repeat":
            trace.append("Rule: repeat request -> say last reply again")
            return s.last_reply or self.greeting()
        if nlu.is_greeting_only(t):
            trace.append("Rule: greeting only -> greet back, no failure counted")
            return self._ask(s, None, "Hello! I can book, change or cancel an appointment. What would you like to do?", trace, state="start")

        if s.state == "done":
            return self._done(s, t, ent, intent, trace)
        if s.state == "confirming":
            return self._confirming(s, t, ent, intent, trace)
        if s.state == "offering":
            return self._offering(s, t, ent, intent, trace)
        return self._collecting(s, t, ent, intent, trace)

    # ------------------------------------------------------------ states
    def _collecting(self, s, t, ent, intent, trace) -> str:
        if intent == "goodbye" and not s.intent:
            return self._goodbye(s, trace)
        if intent == "hours":
            trace.append("Rule: hours question -> answer and keep the current flow")
            return f"{HOURS_TEXT} {s.question}"

        new_intent = intent if intent in ("book", "cancel", "reschedule") else None
        if new_intent and new_intent != s.intent:
            if s.intent:
                trace.append(f"Rule: caller switched {s.intent} -> {new_intent}")
            self._switch_intent(s, new_intent)
            trace.append(f"Decision: start {new_intent} flow")
        elif s.intent is None and ent.has_booking_info():
            s.intent = "book"
            trace.append("Decision: caller gave appointment details without saying why -> assume booking")

        if s.awaiting in ("name", "name_again") and not ent.name and not ent.has_booking_info() and not intent:
            ent.name = nlu.bare_name(t)
            if ent.name:
                trace.append(f"Rule: we just asked for a name, so '{t}' is treated as the name")

        if s.intent is None:
            return self._misunderstood(s, trace, "no intent")

        applied = self._apply(s, ent, trace)
        if not applied and not new_intent:
            requested = nlu.change_request(t)
            if requested and s.intent in ("book", "reschedule"):
                s.slots.pop(requested, None)
                trace.append(f"Rule: caller wants to change {requested} -> ask for it again")
            else:
                return self._misunderstood(s, trace, "nothing usable in the answer")
        s.failures = 0
        return self._advance(s, trace)

    def _offering(self, s, t, ent, intent, trace) -> str:
        alts = s.alternatives
        choice = None
        idx = nlu.ordinal_choice(t)
        if idx is not None and alts:
            choice = alts[idx] if -len(alts) <= idx < len(alts) else None
            trace.append(f"Rule: ordinal/any answer -> picked option {idx + 1 if idx >= 0 else 'last'}")
        elif ent.time and not ent.day:
            matches = [a for a in alts if a[1] == ent.time]
            choice = matches[0] if matches else None
            if choice:
                trace.append("Rule: spoken time matches an offered option")
        if choice:
            s.slots["day"], s.slots["time"] = choice
            s.period, s.alternatives, s.failures = None, [], 0
            s.state = "collecting"
            return self._advance(s, trace)

        if ent.has_booking_info():
            trace.append("Decision: caller gave a new day/time instead of picking -> restart availability check")
            s.alternatives, s.failures = [], 0
            if ent.time:
                s.slots.pop("time", None)
            self._apply(s, ent, trace)
            s.state = "collecting"
            return self._advance(s, trace)

        if nlu.yes_no(t) == "no" or "none" in t:
            s.alternatives = []
            s.state = "collecting"
            s.slots.pop("time", None)
            s.period = None
            return self._ask(s, "time", "No problem. What other day or time would you prefer?", trace)
        return self._misunderstood(s, trace, "no option chosen")

    def _confirming(self, s, t, ent, intent, trace) -> str:
        if ent.has_booking_info() and s.intent != "cancel":
            trace.append("Decision: caller changed details at the confirmation step -> re-validate")
            if ent.time:
                s.slots.pop("time", None)
            self._apply(s, ent, trace)
            s.state = "collecting"
            s.failures = 0
            return self._advance(s, trace)

        answer = nlu.yes_no(t)
        if answer == "yes":
            trace.append("Rule: caller confirmed -> execute")
            return self._execute(s, trace)
        if answer == "no":
            s.failures = 0
            if s.intent == "cancel":
                trace.append("Rule: caller declined cancellation -> keep appointment")
                self._reset_flow(s)
                return self._ask(s, None, "No problem, I've kept your appointment. Is there anything else I can help with?", trace, state="done")
            trace.append("Rule: caller said no -> ask what to change")
            s.state = "collecting"
            return self._ask(s, None, "No problem. What would you like to change: the day, the time or the service?", trace)
        if intent == "goodbye":
            return self._goodbye(s, trace)
        return self._misunderstood(s, trace, "expected yes or no")

    def _done(self, s, t, ent, intent, trace) -> str:
        if intent in ("book", "cancel", "reschedule") or ent.has_booking_info():
            trace.append("Decision: caller wants something else -> new flow")
            self._reset_flow(s)
            return self._collecting(s, t, ent, intent, trace)
        if intent == "hours":
            trace.append("Rule: hours question")
            return f"{HOURS_TEXT} Anything else I can help with?"
        answer = nlu.yes_no(t)
        if intent == "goodbye" or answer == "no":
            return self._goodbye(s, trace)
        if answer == "yes":
            self._reset_flow(s)
            return self._ask(s, None, "Of course. What can I do for you?", trace, state="start")
        return self._misunderstood(s, trace, "unclear after booking")

    # ------------------------------------------------------------ flow logic
    def _switch_intent(self, s: Session, intent: str) -> None:
        name = s.slots.get("name")
        self._reset_flow(s)
        s.slots = {"name": name} if name else {}
        s.intent = intent

    def _reset_flow(self, s: Session) -> None:
        name = s.slots.get("name")
        s.intent, s.period, s.awaiting, s.target = None, None, None, None
        s.alternatives, s.state = [], "start"
        s.slots = {"name": name} if name else {}

    def _apply(self, s: Session, ent: nlu.Entities, trace: list[str]) -> bool:
        applied = False
        for key in ("service", "day", "time", "name"):
            value = getattr(ent, key)
            if value is not None:
                if s.slots.get(key) not in (None, value):
                    trace.append(f"Update: {key} changed from {s.slots[key]} to {value}")
                s.slots[key] = value
                applied = True
        if ent.time:
            s.period = None
        elif ent.period:
            s.period = ent.period
            applied = True
        return applied

    def _advance(self, s: Session, trace: list[str]) -> str:
        if s.intent == "cancel":
            return self._find_target(s, trace)
        if s.intent == "reschedule" and s.target is None:
            return self._find_target(s, trace)
        return self._advance_booking(s, trace)

    def _advance_booking(self, s: Session, trace: list[str], prefix: str = "") -> str:
        now = self.clock()
        sl = s.slots

        d = sl.get("day")
        if d is not None:
            problem = self.schedule.day_problem(d, now.date(), BOOKING_WINDOW_DAYS)
            if problem:
                sl.pop("day")
                trace.append(f"Rule: day {d} rejected ({problem})")
                msg = {"past": "That date has already passed.",
                       "closed": "We're closed on Sundays.",
                       "too_far": "We can only book up to two months ahead."}[problem]
                return self._ask(s, "day", f"{prefix}{msg} What other day works for you?", trace)

        if s.intent == "book" and not sl.get("service"):
            return self._ask(s, "service", f"{prefix}What would you like to come in for? For example {SERVICE_LIST}.", trace)
        if d is None:
            return self._ask(s, "day", f"{prefix}What day would you like? For example tomorrow, next Tuesday, or October 30th.", trace)

        t = sl.get("time")
        if t is None and s.period:
            return self._offer_period(s, d, trace, prefix)
        if t is None:
            return self._ask(s, "time", f"{prefix}What time on {say_day(d)}? We take appointments on the hour.", trace)

        ok, reason = self.schedule.check(d, t, now)
        if not ok:
            sl.pop("time")
            trace.append(f"Rule: {say_time(t)} on {d} unavailable ({reason}) -> offer alternatives")
            return self._offer_alternatives(s, d, t, reason, trace, prefix)

        if not sl.get("name"):
            return self._ask(s, "name", f"{prefix}That time is free. May I have your name for the booking?", trace)
        return self._confirm(s, trace, prefix)

    def _offer_period(self, s: Session, d: date, trace: list[str], prefix: str) -> str:
        now = self.clock()
        period = s.period
        slots = self.schedule.free_slots(d, now, period)[:3]
        if not slots:
            nxt = self.schedule.next_available(d, now, period=period)
            trace.append(f"Rule: nothing free on {d} in the {period}")
            if not nxt:
                s.slots.pop("day", None)
                s.period = None
                return self._ask(s, "day", f"{prefix}Sorry, we have nothing free that {period}. Would another day work?", trace)
            nd, nslots = nxt
            return self._set_offer(s, [(nd, x) for x in nslots],
                                   f"{prefix}Sorry, there's nothing free on {say_day(d)} in the {period}. "
                                   f"The next opening is {say_day(nd)}: {say_list([say_time(x) for x in nslots])}. Would one of those work?", trace)
        trace.append(f"Rule: caller wants the {period} -> offer free slots that day")
        return self._set_offer(s, [(d, x) for x in slots],
                               f"{prefix}On {say_day(d)} in the {period} we have {say_list([say_time(x) for x in slots])}. Which would you like?", trace)

    def _offer_alternatives(self, s: Session, d: date, wanted: time, reason: str, trace, prefix: str) -> str:
        now = self.clock()
        why = {
            "past": "That time has already passed.",
            "outside_hours": "We take appointments nine to twelve and one to five on weekdays, and nine to twelve on Saturdays.",
            "off_grid": "We book on the hour.",
            "taken": f"Sorry, {say_time(wanted)} is already taken.",
        }.get(reason, "Sorry, that time isn't available.")
        near = self.schedule.nearest_free(d, wanted, now)
        if near:
            return self._set_offer(s, [(d, x) for x in near],
                                   f"{prefix}{why} On {say_day(d)} we have {say_list([say_time(x) for x in near])}. Which would you like?", trace)
        nxt = self.schedule.next_available(d, now)
        if not nxt:
            s.slots.pop("day", None)
            return self._ask(s, "day", f"{prefix}{why} Could you try another day?", trace)
        nd, nslots = nxt
        return self._set_offer(s, [(nd, x) for x in nslots],
                               f"{prefix}{why} Nothing else is free on {say_day(d)}. The next opening is "
                               f"{say_day(nd)}: {say_list([say_time(x) for x in nslots])}. Would one of those work?", trace)

    def _set_offer(self, s: Session, alts: list, text: str, trace: list[str]) -> str:
        s.alternatives = alts
        s.state, s.awaiting = "offering", "choice"
        s.question = "Which of those options would you like?"
        trace.append("Next: waiting for the caller to choose one of the offered times")
        return text

    def _confirm(self, s: Session, trace: list[str], prefix: str = "") -> str:
        sl = s.slots
        when = f"{say_day(sl['day'])} at {say_time(sl['time'])}"
        if s.intent == "reschedule" and s.target:
            old = s.target
            text = (f"{prefix}So I'll move your {old.service} from {say_day(old.day)} at {say_time(old.time)} "
                    f"to {when}. Shall I go ahead?")
        else:
            text = (f"{prefix}So that's {article(sl['service'])} {sl['service']} on {when}, under the name "
                    f"{sl['name']}. Shall I book it?")
        s.state, s.awaiting = "confirming", "confirm"
        s.question = "Shall I go ahead? Please say yes or no."
        trace.append("Next: all details collected -> ask for confirmation")
        return text

    def _find_target(self, s: Session, trace: list[str]) -> str:
        name = s.slots.get("name")
        verb = "cancel" if s.intent == "cancel" else "change"
        if not name:
            return self._ask(s, "name", f"Sure. What name is the appointment under?", trace)

        appts = self.schedule.find_by_name(name, self.clock().date())
        if not appts:
            s.slots.pop("name", None)
            s.lookup_failures += 1
            trace.append(f"Rule: no upcoming appointment for '{name}' (failure {s.lookup_failures}/{MAX_FAILURES})")
            if s.lookup_failures >= MAX_FAILURES:
                return self._end(s, "I'm sorry, I can't find that booking. Let me transfer you to our receptionist.")
            return self._ask(s, "name_again", f"I couldn't find an upcoming appointment under {name}. Could you say the name again?", trace)

        if len(appts) > 1:
            picked = [a for a in appts if a.day == s.slots.get("day")] if s.awaiting == "appointment_day" else []
            if len(picked) != 1:
                days = say_list([f"{say_day(a.day)} at {say_time(a.time)}" for a in appts])
                trace.append(f"Rule: {len(appts)} appointments found -> ask which one")
                s.slots.pop("day", None)
                return self._ask(s, "appointment_day", f"I found {len(appts)} appointments under {name}: {days}. Which day is the one you mean?", trace)
            appts = picked
            s.slots.pop("day", None)

        s.lookup_failures = 0
        s.target = appts[0]
        trace.append(f"Decision: matched appointment {s.target.id}")
        found = f"I found your {s.target.service} on {say_day(s.target.day)} at {say_time(s.target.time)}. "
        if s.intent == "cancel":
            s.state, s.awaiting = "confirming", "confirm"
            s.question = "Shall I go ahead? Please say yes or no."
            return f"{found}Do you want me to cancel it?"
        s.slots["service"] = s.target.service
        return self._advance_booking(s, trace, prefix=found)

    def _execute(self, s: Session, trace: list[str]) -> str:
        sl = s.slots
        if s.intent == "cancel" and s.target:
            self.schedule.cancel(s.target.id)
            text = f"Done. Your {s.target.service} on {say_day(s.target.day)} has been cancelled."
        else:
            d, t = sl["day"], sl["time"]
            ok, reason = self.schedule.check(d, t, self.clock())
            if not ok:
                trace.append(f"Rule: slot became unavailable before booking ({reason})")
                s.state = "collecting"
                sl.pop("time", None)
                return self._offer_alternatives(s, d, t, reason, trace, "")
            if s.target:
                self.schedule.cancel(s.target.id)
            appt = self.schedule.book(sl["name"], sl["service"], d, t)
            verb = "moved" if s.intent == "reschedule" else "booked"
            text = (f"You're all set. Your {appt.service} is {verb} for {say_day(appt.day)} at {say_time(appt.time)}. "
                    f"Your confirmation number is {appt.id}.")
        self._reset_flow(s)
        s.failures = 0
        return self._ask(s, None, f"{text} Is there anything else I can help with?", trace, state="done")

    # ------------------------------------------------------------ small helpers
    def _ask(self, s: Session, slot: str | None, text: str, trace: list[str], state: str = "collecting") -> str:
        s.awaiting = slot
        s.state = state
        s.question = text
        trace.append(f"Next: ask for {slot or 'the caller\'s request'}")
        return text

    def _misunderstood(self, s: Session, trace: list[str], why: str) -> str:
        s.failures += 1
        trace.append(f"Rule: not understood ({why}); failure {s.failures}/{MAX_FAILURES}")
        if s.failures >= MAX_FAILURES:
            trace.append("Rule: too many failures -> hand off to a person, end call")
            return self._end(s, "I'm sorry, I'm having trouble understanding. Let me transfer you to our receptionist.")
        return f"Sorry, I didn't catch that. {s.question}"

    def _goodbye(self, s: Session, trace: list[str]) -> str:
        trace.append("Rule: caller is finished -> say goodbye, end call")
        return self._end(s, f"Thank you for calling {CLINIC}. Goodbye!")

    def _end(self, s: Session, text: str) -> str:
        s.ended, s.state = True, "ended"
        return text

    def _result(self, s: Session, reply: str, trace: list[str]) -> TurnResult:
        slots = {k: (v.isoformat() if isinstance(v, (date, time)) else v) for k, v in s.slots.items()}
        if s.period:
            slots["period"] = s.period
        alts = [f"{say_day(d)} at {say_time(t)}" for d, t in s.alternatives]
        return TurnResult(reply, s.state, s.intent, slots, trace, s.ended, alts)
