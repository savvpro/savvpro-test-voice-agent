"""The dialogue manager: the "brain" that decides what to do on every turn.

Plain Python rules and a finite state machine. There is no LLM, no ML model and
no network call anywhere in this file; see DESIGN.md for the full rule table.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

from ..services.scheduler import DAYPARTS, HORIZON_DAYS, LAST_SLOT, OPEN_TIME, Scheduler
from . import formatting as fmt
from .models import DOCTORS, Intent, Session, State, Trace, TurnResult
from .nlu import Parsed, parse
from .phone import is_valid_pk_mobile, normalize_pk

CLINIC = "Green Valley Clinic"
MAX_FAILS = 3  # consecutive misunderstood turns before handing off to a human
LOW_CONFIDENCE = 0.4  # STT confidence below this is treated as "didn't hear"
FLOW_STATES = {State.COLLECTING, State.OFFERING, State.CONFIRMING}

# kind -> (question, example used when the caller is stuck)
PROMPTS: dict[str, tuple[str, str]] = {
    "intent": (
        "Would you like to book, reschedule, or cancel an appointment?",
        "For example, say: book an appointment.",
    ),
    "specialty": ("Which doctor would you like to see: general, dental, or skin?", "For example, say: dental."),
    "day": ("Which day would you like?", "For example, say: tomorrow, or next Monday."),
    "time": ("What time works for you? We're open nine AM to five PM.", "For example, say: four thirty PM."),
    "name": ("May I have your full name, please?", "For example, say: my name is Sara Malik."),
    "phone": (
        "What's your mobile number? Please say all eleven digits.",
        "For example: zero three zero zero, one two three four five six seven.",
    ),
    "phone_lookup": (
        "What phone number is the appointment booked under?",
        "For example: zero three zero zero, one two three four five six seven.",
    ),
    "change": ("What would you like to change: the day, the time, or the doctor?", "For example, say: the time."),
    "other": ("What other day or time would you prefer?", "For example, say: Friday at ten AM."),
    "more": ("Is there anything else I can help you with?", "Please say yes or no."),
    "confirm": ("", "Please say yes to confirm, or no to change something."),
    "offer": ("", "Please say first, second, or third."),
}


class DialogueManager:
    def __init__(self, scheduler: Scheduler, clock: Callable[[], dt.datetime] | None = None):
        self.scheduler = scheduler
        self.clock = clock or scheduler.now

    # ====================================================================== public
    def start(self, s: Session) -> TurnResult:
        trace = Trace(heard="", state_before=s.state.value, rule="start.greeting")
        text = (
            f"Hello, thank you for calling {CLINIC}. I can book, reschedule, or cancel "
            "an appointment. What would you like to do?"
        )
        s.pending, s.last_prompt, s.last_example = "intent", text, PROMPTS["intent"][1]
        return self._finish(s, trace, text)

    def handle(self, s: Session, utterance: str, confidence: float | None = None) -> TurnResult:
        s.turns += 1
        trace = Trace(heard=utterance, state_before=s.state.value)
        if s.state in (State.ENDED, State.HANDOFF):
            trace.rule = "terminal.already_ended"
            return self._finish(s, trace, "This call has ended. Goodbye.")
        reply = self._dispatch(s, utterance.strip(), confidence, trace)
        return self._finish(s, trace, reply)

    # ===================================================================== routing
    def _finish(self, s: Session, trace: Trace, reply: str) -> TurnResult:
        s.last_reply = reply
        trace.state_after = s.state.value
        return TurnResult(reply=reply, trace=trace, session=s)

    def _dispatch(self, s: Session, text: str, confidence: float | None, trace: Trace) -> str:
        if not text:
            return self._not_understood(s, trace, "silence")
        if confidence is not None and confidence < LOW_CONFIDENCE:
            trace.note(f"STT confidence {confidence:.2f} below {LOW_CONFIDENCE}")
            return self._not_understood(s, trace, "low_confidence")

        p = parse(text, self.clock().date(), expecting=s.pending)
        trace.intents, trace.entities = p.labels(), p.entities()

        # 1. global commands work in every state
        if p.human:
            return self._handoff(
                s, trace, "global.human_requested", "Of course. I'll transfer you to our receptionist now. Please hold."
            )
        if p.repeat:
            trace.rule = "global.repeat"
            return s.last_reply or s.last_prompt
        if p.restart:
            return self._restart(s, trace)
        if p.goodbye:
            return self._goodbye(s, trace)
        if p.faq:
            return self._faq(s, trace, p)
        in_flow = s.state in FLOW_STATES
        if in_flow and p.abort:
            return self._abort(s, trace)

        # 2. the caller changes their mind about *what* they want
        if in_flow and p.primary_intent in (Intent.RESCHEDULE, Intent.CANCEL) and p.primary_intent != s.intent:
            if p.primary_intent == Intent.CANCEL and s.intent == Intent.BOOK and not p.mentions_existing:
                trace.note('"cancel" during a booking means: drop this booking')
                return self._abort(s, trace)
            return self._switch_intent(s, p, trace)

        # 3. per-state handlers
        handler = {
            State.ASK_INTENT: self._on_ask_intent,
            State.COLLECTING: self._on_collecting,
            State.OFFERING: self._on_offering,
            State.CONFIRMING: self._on_confirming,
            State.ASK_MORE: self._on_ask_more,
        }[s.state]
        return handler(s, p, trace)

    # ================================================================ state handlers
    def _on_ask_intent(self, s: Session, p: Parsed, trace: Trace) -> str:
        intent = p.primary_intent
        if intent is None and (p.day or p.at or p.specialty or p.daypart):
            intent = Intent.BOOK
            trace.note("no intent word but a slot was given: assuming BOOK")
        if intent is None:
            return self._not_understood(s, trace, "unclear")
        s.intent, s.state, s.fails = intent, State.COLLECTING, 0
        trace.rule = f"ask_intent.set_{intent.value}"
        self._apply_entities(s, p, trace)
        return self._advance(s, trace)

    def _on_collecting(self, s: Session, p: Parsed, trace: Trace) -> str:
        trace.rule = "collecting.fill_slots"
        recognised, _ = self._apply_entities(s, p, trace)
        if s.pending == "change":
            recognised |= self._apply_change_words(s, p, trace)
        if p.change_day:
            s.slots.day, s.offers, recognised = None, [], True
        if p.change_time:
            s.slots.at, s.offers, recognised = None, [], True
        if not recognised:
            return self._not_understood(s, trace, "unclear")
        s.fails = 0
        return self._advance(s, trace)

    def _on_offering(self, s: Session, p: Parsed, trace: Trace) -> str:
        trace.rule = "offering.choose"
        offers, pick = s.offers, None
        if p.choice is not None and (p.choice == -1 or p.choice <= len(offers)):
            pick = offers[p.choice - 1 if p.choice > 0 else -1]
        elif p.at is not None:
            matches = [o for o in offers if o.time() == p.at and (p.day is None or o.date() == p.day)]
            pick = matches[0] if matches else None
        elif p.yes and len(offers) == 1:
            pick = offers[0]
        if pick is not None:
            s.slots.day, s.slots.at, s.offers, s.fails = pick.date(), pick.time(), [], 0
            s.state = State.COLLECTING
            trace.note(f"caller picked {pick:%a %H:%M}")
            return self._advance(s, trace)
        if p.day or p.at or p.specialty or p.daypart:
            trace.note("caller asked for something new instead of choosing an offer")
            self._apply_entities(s, p, trace)
            s.offers, s.fails = [], 0
            s.state = State.COLLECTING
            return self._advance(s, trace)
        if p.yes:
            return self._ask(s, "offer", "Which one would you like: the first, second, or third?")
        if p.no:
            s.slots.at, s.offers, s.fails = None, [], 0
            s.state = State.COLLECTING
            return "No problem. " + self._ask(s, "other")
        return self._not_understood(s, trace, "unclear")

    def _on_confirming(self, s: Session, p: Parsed, trace: Trace) -> str:
        recognised, changed = self._apply_entities(s, p, trace)
        wants_change = p.change_day or p.change_time
        if p.change_day:
            s.slots.day = None
        if p.change_time:
            s.slots.at = None
        if changed or wants_change:
            trace.rule = "confirming.correction"
            s.fails = 0
            return self._advance(s, trace)  # re-validate everything, then re-confirm
        if p.yes or (recognised and not p.no):
            trace.rule = "confirming.accepted"
            s.fails = 0
            return self._execute(s, trace)
        if p.no:
            s.fails = 0
            if s.intent == Intent.CANCEL:
                trace.rule = "confirming.declined_cancel"
                return self._done(s, "Okay, I've left your appointment as it is.")
            trace.rule = "confirming.declined"
            s.state = State.COLLECTING
            return "No problem. " + self._ask(s, "change")
        return self._not_understood(s, trace, "unclear")

    def _on_ask_more(self, s: Session, p: Parsed, trace: Trace) -> str:
        if p.primary_intent or p.day or p.at or p.specialty:
            return self._on_ask_intent(s, p, trace)
        if p.no:
            return self._goodbye(s, trace)
        if p.yes:
            trace.rule = "ask_more.yes"
            s.state, s.fails = State.ASK_INTENT, 0
            return self._ask(s, "intent", "Sure. Would you like to book, reschedule, or cancel an appointment?")
        return self._not_understood(s, trace, "unclear")

    # ================================================================ slot handling
    def _apply_entities(self, s: Session, p: Parsed, trace: Trace) -> tuple[bool, bool]:
        """Copy entities into the session. Returns (recognised anything, changed a value)."""
        recognised = changed = False
        sl = s.slots

        def put(field: str, new: object) -> None:
            nonlocal recognised, changed
            if new is None:
                return
            recognised = True
            old = getattr(sl, field)
            if old != new:
                changed = True
                if old is not None:
                    trace.note(f"correction: {field} {old} -> {new}")
                    self._acknowledge(s, field, new)
                setattr(sl, field, new)

        if s.existing is None:  # rescheduling keeps the original doctor and patient
            put("specialty", p.specialty)
            if s.intent == Intent.BOOK or s.intent is None:
                put("name", p.name)
        put("day", p.day)
        put("at", p.at)
        if p.phone is not None:
            recognised = True
            candidate = p.phone if p.phone_valid else None
            if candidate is None and s.phone_partial:
                joined = normalize_pk(s.phone_partial + p.phone)  # speech engines often split a number in two
                if is_valid_pk_mobile(joined):
                    trace.note(f"joined digits {s.phone_partial} + {p.phone}")
                    candidate = joined
            if candidate is not None:
                s.phone_problem, s.phone_partial = False, ""
                put("phone", candidate)
            else:
                s.phone_problem = True
                combined = s.phone_partial + p.phone
                s.phone_partial = p.phone if len(combined) > 11 else combined
                trace.note(f"heard {len(p.phone)} digits; need an 11-digit mobile number")
        if p.vague_date and sl.day is None:
            s.vague_date, recognised = True, True
        if p.daypart:
            s.daypart, recognised = p.daypart, True
        if p.at is not None:
            s.daypart = None  # an exact time beats "morning"
        if p.day is not None or p.at is not None:
            s.offers = []
        return recognised, changed

    def _acknowledge(self, s: Session, field: str, new: object) -> None:
        """Say out loud that a previously given value was replaced."""
        today = self.clock().date()
        spoken = {
            "day": lambda: fmt.say_date(new, today),  # type: ignore[arg-type]
            "at": lambda: fmt.say_time(new),  # type: ignore[arg-type]
            "specialty": lambda: f"{DOCTORS[str(new)].label} with {DOCTORS[str(new)].name}",
        }.get(field)
        if spoken:
            self._add_notice(s, f"Okay, {spoken()}.")

    @staticmethod
    def _add_notice(s: Session, text: str) -> None:
        s.notice = f"{s.notice} {text}" if s.notice else text

    def _apply_change_words(self, s: Session, p: Parsed, trace: Trace) -> bool:
        hit = False
        for words, field in (
            ({"day", "date"}, "day"),
            ({"time", "hour"}, "at"),
            ({"doctor", "dentist", "specialist", "service"}, "specialty"),
            ({"name"}, "name"),
            ({"number", "phone"}, "phone"),
        ):
            if p.words & words:
                if field == "specialty" and s.existing is not None:
                    continue
                setattr(s.slots, field, None)
                trace.note(f"caller wants to change: {field}")
                hit = True
        return hit

    # ---------------------------------------------------------------- the main loop
    def _advance(self, s: Session, trace: Trace) -> str:
        """Ask for the next missing piece, or move on to confirmation."""
        s.state = State.COLLECTING
        reply = self._advance_inner(s, trace)
        if s.notice:
            reply, s.notice = f"{s.notice} {reply}", None
        return reply

    def _advance_inner(self, s: Session, trace: Trace) -> str:
        sl = s.slots
        if s.intent in (Intent.RESCHEDULE, Intent.CANCEL):
            early = self._ensure_appointment(s, trace)
            if early is not None:
                return early
            if s.intent == Intent.CANCEL:
                return self._confirm_cancel(s, trace)
        elif sl.specialty is None:
            trace.rule = "advance.ask_specialty"
            return self._ask(s, "specialty")

        early = self._datetime_step(s, trace)
        if early is not None:
            return early

        if s.intent == Intent.BOOK:
            if sl.name is None:
                trace.rule = "advance.ask_name"
                return self._ask(s, "name")
            if sl.phone is None:
                trace.rule = "advance.ask_phone"
                if s.phone_problem:
                    return self._phone_retry(s, "phone")
                return self._ask(s, "phone")
            clash = self._same_day_booking(s)
            if clash is not None:
                trace.rule = "advance.duplicate_booking"
                s.reset_flow(keep_contact=True)
                s.state = State.ASK_INTENT
                today = self.clock().date()
                return self._ask(
                    s,
                    "intent",
                    f"You already have an appointment with {DOCTORS[clash.specialty].name} "
                    f"{fmt.on_date(clash.start.date(), today)} at {fmt.say_time(clash.start.time())}. "
                    "To change it, say reschedule. Otherwise, what would you like to do?",
                )
            return self._confirm_booking(s, trace)
        return self._confirm_reschedule(s, trace)

    def _datetime_step(self, s: Session, trace: Trace) -> str | None:
        """Validate day/time and check availability. Returns a reply, or None if all is well."""
        sl, now = s.slots, self.clock()
        today, notes = now.date(), []

        if sl.day is not None:
            problem = self._day_problem(sl.day, today)
            if problem:
                trace.rule = "advance.invalid_day"
                notes.append(problem)
                sl.day = None
        if sl.day is None:
            trace.rule = trace.rule if notes else "advance.ask_day"
            text = "Which day would you like? We're open Monday to Saturday." if s.vague_date else None
            s.vague_date = False
            return " ".join(notes + [self._ask(s, "day", text)])

        if sl.at is None and s.daypart:
            lo, hi = DAYPARTS[s.daypart]
            free = [x for x in self.scheduler.free_slots(sl.specialty, sl.day) if lo <= x.time() <= hi]
            if free:
                trace.rule = "advance.offer_daypart"
                s.offers, s.state = free[:3], State.OFFERING
                return self._ask(
                    s,
                    "offer",
                    f"For the {s.daypart}, I have {fmt.say_offers(s.offers, today)}. Which would you like?",
                )
            notes.append(f"I don't have any {s.daypart} openings {fmt.on_date(sl.day, today)}.")
            s.daypart, sl.day = None, None
            trace.rule = "advance.daypart_full"
            return " ".join(notes + [self._ask(s, "day", "Would another day work?")])
        if sl.at is None:
            trace.rule = "advance.ask_time"
            return self._ask(s, "time")

        problem = self._time_problem(sl.at, sl.day, now)
        if problem:
            trace.rule = "advance.invalid_time"
            sl.at = None
            return f"{problem} " + self._ask(s, "time", "What time works for you?")

        start = dt.datetime.combine(sl.day, sl.at)
        if s.existing is not None and start == s.existing.start:
            trace.rule = "advance.same_as_current"
            sl.at = None
            return "That's already the time of your appointment. " + self._ask(
                s, "time", "Which other time would you like?"
            )
        if self.scheduler.is_free(sl.specialty, start):
            trace.note("slot is free")
            return None

        alternatives = self.scheduler.alternatives(sl.specialty, start, n=3)
        if not alternatives:
            trace.rule = "advance.no_availability"
            sl.day, sl.at = None, None
            return "I'm sorry, I don't see any openings in the next week. " + self._ask(
                s, "day", "Would you like to try a different week?"
            )
        trace.rule = "advance.slot_taken_offer_alternatives"
        s.offers, s.state = alternatives, State.OFFERING
        reason = (
            "Appointments start on the hour or half hour."
            if sl.at.minute % 30
            else f"I'm sorry, {fmt.say_time(sl.at)} {fmt.on_date(sl.day, today)} isn't available."
        )
        return self._ask(
            s,
            "offer",
            f"{reason} The nearest openings are {fmt.say_offers(alternatives, today)}. Which would you like?",
        )

    @staticmethod
    def _day_problem(day: dt.date, today: dt.date) -> str | None:
        if day < today:
            return "That date has already passed."
        if day > today + dt.timedelta(days=HORIZON_DAYS):
            return "I can only book up to thirty days ahead."
        if day.weekday() == 6:
            return "We're closed on Sundays."
        return None

    @staticmethod
    def _time_problem(at: dt.time, day: dt.date, now: dt.datetime) -> str | None:
        if not OPEN_TIME <= at <= LAST_SLOT:
            return "Appointments run from nine AM to four thirty PM."
        if day == now.date() and at <= now.time():
            return "That time has already passed today."
        return None

    def _same_day_booking(self, s: Session):
        sl = s.slots
        for appt in self.scheduler.find_by_phone(sl.phone or ""):
            if appt.specialty == sl.specialty and appt.start.date() == sl.day:
                return appt
        return None

    # ----------------------------------------------------- reschedule / cancel lookup
    def _ensure_appointment(self, s: Session, trace: Trace) -> str | None:
        if s.existing is not None:
            return None
        sl = s.slots
        if sl.phone is None:
            trace.rule = "lookup.ask_phone"
            if s.phone_problem:
                return self._phone_retry(s, "phone_lookup")
            return self._ask(s, "phone_lookup")
        found = self.scheduler.find_by_phone(sl.phone)
        if not found:
            s.lookup_attempts += 1
            sl.phone = None
            trace.rule = "lookup.not_found"
            if s.lookup_attempts >= 2:
                return self._handoff(
                    s,
                    trace,
                    "lookup.not_found_handoff",
                    "I still can't find an appointment under that number, so I'll transfer you to our receptionist.",
                )
            return self._ask(
                s,
                "phone_lookup",
                "I couldn't find an upcoming appointment under that number. Could you say the number again?",
            )
        appt = found[0]
        s.existing, sl.specialty, sl.name = appt, appt.specialty, appt.name
        today = self.clock().date()
        trace.rule = "lookup.found"
        doc = DOCTORS[appt.specialty]
        if s.intent == Intent.RESCHEDULE:
            self._add_notice(
                s,
                f"Thank you, {appt.name}. I found your {doc.label} appointment with {doc.name} "
                f"{fmt.on_date(appt.start.date(), today)} at {fmt.say_time(appt.start.time())}. Let's find a new time.",
            )
        else:  # the cancel confirmation question already repeats the details
            self._add_notice(s, f"Thank you, {appt.name}.")
        return None

    # ------------------------------------------------------------------ confirmations
    def _confirm_booking(self, s: Session, trace: Trace) -> str:
        sl, today = s.slots, self.clock().date()
        doc = DOCTORS[sl.specialty or "general"]
        s.state = State.CONFIRMING
        trace.rule = "advance.confirm_booking"
        return self._ask(
            s,
            "confirm",
            f"Let me confirm: a {doc.label} appointment with {doc.name} {fmt.on_date(sl.day, today)} "
            f"at {fmt.say_time(sl.at)}, for {sl.name}, phone number {fmt.say_phone(sl.phone or '')}. Shall I book it?",
        )

    def _confirm_reschedule(self, s: Session, trace: Trace) -> str:
        sl, old, today = s.slots, s.existing, self.clock().date()
        assert old is not None
        s.state = State.CONFIRMING
        trace.rule = "advance.confirm_reschedule"
        return self._ask(
            s,
            "confirm",
            f"I'll move your appointment with {DOCTORS[old.specialty].name} from "
            f"{fmt.say_date(old.start.date(), today)} at {fmt.say_time(old.start.time())} to "
            f"{fmt.say_date(sl.day, today)} at {fmt.say_time(sl.at)}. Shall I go ahead?",
        )

    def _confirm_cancel(self, s: Session, trace: Trace) -> str:
        old, today = s.existing, self.clock().date()
        assert old is not None
        s.state = State.CONFIRMING
        trace.rule = "advance.confirm_cancel"
        doc = DOCTORS[old.specialty]
        return self._ask(
            s,
            "confirm",
            f"You'd like to cancel your {doc.label} appointment with {doc.name} "
            f"{fmt.on_date(old.start.date(), today)} at {fmt.say_time(old.start.time())}. Is that right?",
        )

    # --------------------------------------------------------------------- execution
    def _execute(self, s: Session, trace: Trace) -> str:
        sl, today = s.slots, self.clock().date()
        if s.intent == Intent.CANCEL:
            assert s.existing is not None
            self.scheduler.cancel(s.existing.id)
            trace.rule = "execute.cancel"
            return self._done(s, "Your appointment has been cancelled.")

        start = dt.datetime.combine(sl.day, sl.at)  # type: ignore[arg-type]
        if s.intent == Intent.RESCHEDULE:
            assert s.existing is not None
            appt = self.scheduler.reschedule(s.existing.id, start)
            verb, trace.rule = "moved", "execute.reschedule"
        else:
            appt = self.scheduler.book(sl.name or "", sl.phone or "", sl.specialty or "general", start)
            verb, trace.rule = "booked", "execute.book"
        if appt is None:
            trace.rule = "execute.slot_lost"
            sl.at = None
            s.state = State.COLLECTING
            return "I'm sorry, that slot was just taken. " + self._advance(s, trace)
        doc = DOCTORS[appt.specialty]
        return self._done(
            s,
            f"You're all set. Your {doc.label} appointment with {doc.name} is {verb} for "
            f"{fmt.say_date(start.date(), today)} at {fmt.say_time(start.time())}. "
            f"Your confirmation number is {fmt.say_digits(str(appt.id))}.",
        )

    def _done(self, s: Session, message: str) -> str:
        s.reset_flow(keep_contact=True)
        s.state = State.ASK_MORE
        return f"{message} " + self._ask(s, "more")

    # ======================================================================= helpers
    def _phone_retry(self, s: Session, kind: str) -> str:
        """Ask again after a bad number. Silence re-prompts repeat the plain question, not the complaint."""
        s.phone_problem = False
        if 0 < len(s.phone_partial) < 11:
            text = f"I have {fmt.say_digits(s.phone_partial)} so far. Please say the remaining digits."
            reply = self._ask(s, kind, text)
            return reply
        s.phone_partial = ""
        reply = self._ask(
            s, kind, "That doesn't sound like a full eleven digit mobile number. Please say it again, digit by digit."
        )
        s.last_prompt = PROMPTS[kind][0]
        return reply

    def _ask(self, s: Session, kind: str, text: str | None = None) -> str:
        question, example = PROMPTS.get(kind, ("", ""))
        text = text or question
        s.pending, s.last_prompt, s.last_example = kind, text, example
        return text

    def _not_understood(self, s: Session, trace: Trace, reason: str) -> str:
        s.fails += 1
        trace.rule = f"fallback.reprompt_{s.fails}"
        trace.note(f"not understood ({reason}); consecutive failures = {s.fails}")
        if s.fails >= MAX_FAILS:
            return self._handoff(
                s,
                trace,
                "fallback.handoff",
                "I'm having trouble understanding you, so I'll transfer you to our receptionist. Goodbye.",
            )
        short = s.pending in ("confirm", "offer")
        if s.fails == 1:
            lead = {
                "silence": "I didn't hear anything.",
                "low_confidence": "I'm not sure I caught that.",
            }.get(reason, "Sorry, I didn't understand that.")
            # long read-backs are not repeated in full on the first retry
            return f"{lead} {s.last_example if short else s.last_prompt}"
        if short:
            return f"Let me try again. {s.last_prompt}"
        return f"Let me try again. {s.last_prompt} {s.last_example}".strip()

    def _handoff(self, s: Session, trace: Trace, rule: str, message: str) -> str:
        trace.rule, s.state = rule, State.HANDOFF
        return message

    def _goodbye(self, s: Session, trace: Trace) -> str:
        trace.rule = "global.goodbye"
        unfinished = s.state in FLOW_STATES
        s.state = State.ENDED
        lead = "Okay, I haven't made any changes. " if unfinished else ""
        return f"{lead}Thank you for calling {CLINIC}. Goodbye!"

    def _restart(self, s: Session, trace: Trace) -> str:
        trace.rule = "global.restart"
        s.reset_flow(keep_contact=False)
        s.state, s.fails = State.ASK_INTENT, 0
        return "Okay, let's start over. " + self._ask(s, "intent")

    def _abort(self, s: Session, trace: Trace) -> str:
        trace.rule = "global.abort"
        s.reset_flow(keep_contact=True)
        s.state, s.fails = State.ASK_MORE, 0
        return "No problem, I've dropped that. " + self._ask(s, "more")

    def _switch_intent(self, s: Session, p: Parsed, trace: Trace) -> str:
        assert p.primary_intent is not None
        trace.rule = f"global.switch_to_{p.primary_intent.value}"
        s.reset_flow(keep_contact=True)
        s.intent, s.state, s.fails = p.primary_intent, State.COLLECTING, 0
        self._apply_entities(s, p, trace)
        return self._advance(s, trace)

    def _faq(self, s: Session, trace: Trace, p: Parsed) -> str:
        trace.rule = f"global.faq_{p.faq}"
        answer = (
            f"{CLINIC} is open Monday to Saturday, nine AM to five PM, and closed on Sundays."
            if p.faq == "hours"
            else f"{CLINIC} is at 12 Main Boulevard, Lahore."
        )
        return f"{answer} {s.last_prompt}".strip()
