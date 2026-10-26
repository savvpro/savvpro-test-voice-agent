"""The dialogue manager: decides what to say and do on every turn.

Rules, in order, each turn:
  1. emergency          -> emergency advice, end call
  2. human_agent        -> hand off (also after 3 misunderstood turns in a row)
  3. abort              -> drop the current task
  4. repeat             -> resend the last prompt
  5. picking one of the offered slots ("the second one", "10:40")
  6. clinic info / small talk -> answer, then return to where we were
  7. merge entities into the frame at ANY state, acknowledging changed values
  8. validate (policies), then ask for the next missing thing, offer slots,
     or confirm; on "yes" at confirmation, write to the database.
"""

import datetime as dt
import re
from collections.abc import Callable

from pydantic import BaseModel

from app.clinic import OPENING_HOURS
from app.db.models import AppointmentStatus, Slot
from app.db.repository import AppointmentNotFoundError, ClinicRepository, SlotUnavailableError
from app.dialogue import policies
from app.dialogue.frame import FoundAppointment, Frame, SlotOption, Task
from app.dialogue.responses import (
    Responses,
    format_date,
    format_phone,
    format_slot,
    format_time,
    join_words,
    opening_hours_text,
    spell_ref,
    weekday_name,
)
from app.dialogue.states import TERMINAL_STATES, State
from app.nlu.entities import Entities
from app.nlu.normalizer import MONTHS
from app.nlu.pipeline import FALLBACK_INTENT, NLUResult

# expected_slot after "what would you like to change?" (not an entity slot)
CHANGE_WHICH = "change_which"
MAX_FAILURES = 3
MAX_SILENCES = 3

TASK_INTENTS: dict[str, Task] = {
    "book_appointment": "book",
    "check_availability": "book",  # availability answers flow straight into booking
    "reschedule_appointment": "reschedule",
    "cancel_appointment": "cancel",
}
INFO_INTENTS = {"clinic_hours", "clinic_location", "list_departments", "list_doctors"}
# Only these intents may write entities into the frame: a date inside
# "what time do you close on saturday?" must not change the booking date.
SLOT_INTENTS = {"inform", "change_request", "affirm", "deny", FALLBACK_INTENT, *TASK_INTENTS}

_FIELD_LABELS = {
    "department": "department",
    "doctor": "doctor",
    "date": "date",
    "time": "time",
    "time_of_day": "time",
    "patient_name": "name",
    "phone": "phone number",
    "booking_ref": "booking reference",
}
# "change the time" / "the date" -> which slot to clear and ask for again
_NAMED_FIELDS = [
    ("department", r"department|specialist|specialty|speciality"),
    ("doctor", r"doctor|dr"),
    ("date", r"date|day"),
    ("time", r"time|slot"),
    ("patient_name", r"name"),
    ("phone", r"number|phone|mobile"),
]
_CHOICE = re.compile(
    r"\b(?:option|number) ([1-3])\b"
    r"|\b(first|second|third|1st|2nd|3rd|last|earliest|latest)\b(?! of\b)"
)
_CHOICE_INDEX = {
    "first": 0, "1st": 0, "earliest": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2,
    "last": -1, "latest": -1,
}  # fmt: skip
_MONTH = re.compile(r"\b(?:" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b")


class Decision(BaseModel):
    reply_text: str
    state: State
    frame: Frame
    action: str | None = None
    end_call: bool = False
    expected_slot: str | None = None


def _option(slot: Slot) -> SlotOption:
    return SlotOption(
        slot_id=slot.id,
        start=slot.start_time,
        doctor=slot.doctor.name,
        department=slot.doctor.department.name,
    )


class DialogueManager:
    def __init__(
        self,
        repo: ClinicRepository,
        now: Callable[[], dt.datetime] | None = None,
        seed: int | None = 0,
    ):
        self.repo = repo
        self.now = now or repo.now
        self.say = Responses(seed)

    # --- entry points ----------------------------------------------------

    def start(self, frame: Frame) -> Decision:
        frame.state = State.IDENTIFY_TASK
        return self._reply(frame, self.say("greeting"))

    def handle(self, nlu: NLUResult, frame: Frame) -> Decision:
        decision = self._handle(nlu, frame)
        if decision.action not in ("not_understood", "silence"):
            frame.fail_count = decision.frame.fail_count = 0
        return decision

    # --- turn logic --------------------------------------------------------

    def _handle(self, nlu: NLUResult, frame: Frame) -> Decision:
        if frame.state in TERMINAL_STATES:
            return self._reply(frame, self.say("call_over"), end_call=True, remember=False)
        if not nlu.normalized_text:
            return self._silence(frame)
        frame.silence_count = 0
        intent = nlu.intent

        if intent == "emergency":
            frame.state = State.EMERGENCY
            frame.expected_slot = None
            return self._reply(frame, self.say("emergency"), action="emergency", end_call=True)
        if intent == "human_agent":
            return self._handoff(frame, "handoff")
        if intent == "abort":
            frame.reset_task()
            frame.state = State.IDENTIFY_TASK
            frame.expected_slot = None
            text = f"{self.say('aborted')} {self.say('anything_else')}"
            return self._reply(frame, text, action="aborted")
        if intent == "repeat":
            return self._reply(frame, frame.last_prompt or self.say("greeting"), remember=False)
        if intent == "goodbye":
            frame.state = State.END
            frame.expected_slot = None
            return self._reply(frame, self.say("goodbye"), action="ended", end_call=True)

        if frame.state == State.OFFER_SLOTS:
            picked = self._pick_option(nlu, frame)
            if picked is not None:
                self._choose(frame, frame.candidate_slots[picked])
                return self._advance(frame, [])
            if intent == "affirm":
                ordinals = ["the first", "the second", "the third"]
                choices = join_words(ordinals[: len(frame.candidate_slots)], "or")
                return self._reply(frame, self.say("which_option", choices=choices), remember=False)
            if intent == "deny":
                frame.clear_selection()
                frame.date = frame.time = frame.time_of_day = None
                return self._reply(frame, self._ask(frame, "offer_declined", "date"))

        if intent in INFO_INTENTS:
            return self._answer_info(intent, nlu.entities, frame)
        if intent == "out_of_scope":
            return self._continue(frame, self.say("out_of_scope"))
        if intent == "greet":
            return self._continue(frame, self.say("hello_again"))
        if intent == "thank_you":
            return self._continue(frame, self.say("welcome"))

        notes: list[str] = []
        task = TASK_INTENTS.get(intent)
        if task:
            self._start_task(frame, task, intent)
        understood = self._merge(nlu.entities, frame, notes) if intent in SLOT_INTENTS else False
        if nlu.entities.unknown_department and not nlu.entities.department:
            notes.append(self.say("unknown_department", name=nlu.entities.unknown_department))
            understood = True

        if frame.state == State.CONFIRM and not understood and task in (None, frame.task):
            return self._at_confirm(nlu, frame)

        if not understood and not task:
            if (
                frame.task
                and self._wants_change(nlu, frame)
                and self._clear_named_field(nlu, frame)
            ):
                return self._advance(frame, notes)
            if intent in ("affirm", "deny") and frame.task:
                return self._advance(frame, notes)
            if intent == "affirm":
                return self._reply(frame, self.say("how_can_i_help"))
            if intent == "deny" and frame.state in (State.DONE, State.IDENTIFY_TASK):
                frame.state = State.END
                return self._reply(frame, self.say("goodbye"), action="ended", end_call=True)
            return self._not_understood(frame, nlu)

        if frame.task is None:
            if any(getattr(frame, f) for f in ("department", "doctor", "date", "time")) or (
                frame.time_of_day or nlu.entities.unknown_department
            ):
                self._start_task(frame, "book", None)
            elif frame.booking_ref or frame.phone:
                frame.state = State.IDENTIFY_TASK
                frame.expected_slot = None
                return self._reply(frame, " ".join([*notes, self.say("change_or_cancel")]))
            else:
                return self._reply(frame, " ".join([*notes, self.say("how_can_i_help")]))
        return self._advance(frame, notes)

    # --- frame updates -------------------------------------------------------

    def _start_task(self, frame: Frame, task: Task, intent: str | None) -> None:
        if intent == "check_availability" and frame.task:
            return  # "is 4 free?" while booking/rescheduling stays in that task
        if frame.task == task:
            return
        if frame.task is not None or frame.state == State.DONE:
            frame.reset_task()
        frame.task = task
        frame.state = State.COLLECT_SLOTS

    def _merge(self, e: Entities, frame: Frame, notes: list[str]) -> bool:
        """Copy entities into the frame. Returns True if the turn carried any slot value."""
        found = False

        def put(field: str, value, shown: str) -> bool:
            nonlocal found
            if value is None:
                return False
            found = True
            old = getattr(frame, field)
            if old == value:
                return False
            if old is not None:
                notes.append(self.say("changed", what=_FIELD_LABELS[field], value=shown))
            setattr(frame, field, value)
            return True

        if put("doctor", e.doctor, e.doctor or ""):
            frame.department = self.repo.doctor_department(e.doctor) or frame.department
            frame.clear_selection()
        elif put("department", e.department, e.department or ""):
            if frame.doctor and self.repo.doctor_department(frame.doctor) != frame.department:
                frame.doctor = None
            frame.clear_selection()
        if e.date and put("date", e.date, format_date(e.date)):
            frame.clear_selection()
        if e.time and put("time", e.time, format_time(e.time)):
            frame.time_of_day = None
            frame.clear_selection()
        elif e.time_of_day and not e.time:
            if put("time_of_day", e.time_of_day, e.time_of_day.label):
                frame.time = None
                frame.clear_selection()
        put("patient_name", e.patient_name, e.patient_name or "")
        put("phone", e.phone, format_phone(e.phone) if e.phone else "")
        if put("booking_ref", e.booking_ref, e.booking_ref or ""):
            frame.appointment = None
        return found

    @staticmethod
    def _wants_change(nlu: NLUResult, frame: Frame) -> bool:
        # Only a change request, or the answer to "what would you like to change?",
        # names a field to redo -- "my number is 0321" is a bad phone number, not that.
        return nlu.intent == "change_request" or frame.expected_slot == CHANGE_WHICH

    def _clear_named_field(self, nlu: NLUResult, frame: Frame) -> bool:
        """'change the time' / 'the date' -> forget that slot so it gets asked again."""
        if frame.task == "cancel":
            return False
        for field, pattern in _NAMED_FIELDS:
            if re.search(rf"\b(?:{pattern})\b", nlu.normalized_text):
                if field == "time":
                    frame.time = frame.time_of_day = None
                elif field == "department":
                    frame.department = frame.doctor = None
                else:
                    setattr(frame, field, None)
                frame.clear_selection()
                return True
        return False

    def _pick_option(self, nlu: NLUResult, frame: Frame) -> int | None:
        options = frame.candidate_slots
        text = nlu.normalized_text
        if not _MONTH.search(text):  # "the 2nd of February" is a date, not option 2
            m = _CHOICE.search(text)
            if m:
                index = int(m[1]) - 1 if m[1] else _CHOICE_INDEX[m[2]]
                if -len(options) <= index < len(options):
                    return index % len(options)
        wanted = nlu.entities.time
        if wanted:
            for i, option in enumerate(options):
                same_day = nlu.entities.date in (None, option.start.date())
                if option.start.time() == wanted and same_day:
                    return i
        if nlu.intent == "affirm" and len(options) == 1:
            return 0
        return None

    def _choose(self, frame: Frame, option: SlotOption) -> None:
        frame.chosen_slot = option
        frame.candidate_slots = []
        frame.date = option.start.date()
        frame.time = option.start.time()
        frame.time_of_day = None
        frame.doctor = option.doctor
        frame.department = option.department

    # --- planning: what to ask next ------------------------------------------

    def _advance(self, frame: Frame, notes: list[str]) -> Decision:
        if frame.task == "book":
            text = self._slot_step(frame) or self._details_step(frame)
        elif frame.task == "reschedule":
            text = (
                self._lookup_step(frame, notes)
                or self._slot_step(frame)
                or self._confirm_reschedule(frame)
            )
        else:
            text = self._lookup_step(frame, notes) or self._confirm_cancel(frame)
        return self._reply(frame, " ".join([*notes, text]))

    def _ask(self, frame: Frame, key: str, expected: str | None, **values) -> str:
        frame.state = State.LOOKUP_BOOKING if expected == "booking_ref" else State.COLLECT_SLOTS
        frame.expected_slot = expected
        return self.say(key, **values)

    def _slot_step(self, frame: Frame) -> str | None:
        """Find the appointment slot. Returns a prompt, or None once a slot is chosen."""
        if frame.chosen_slot:
            return None
        if not frame.department:
            departments = join_words(self.repo.department_names())
            return self._ask(frame, "ask_department", "department", departments=departments)
        if not frame.date:
            return self._ask(frame, "ask_date", "date")

        now = self.now()
        problem = policies.check_date(frame.date, now.date())
        if problem:
            day, frame.date = frame.date, None
            return self._ask(frame, problem, "date", date=format_date(day))

        if frame.time:
            problem = policies.check_time(frame.date, frame.time, now)
            if problem:
                at, frame.time = frame.time, None
                close = OPENING_HOURS[frame.date.weekday()][-1][1]
                return self._ask(
                    frame,
                    problem,
                    "time",
                    time=format_time(at),
                    weekday=weekday_name(frame.date),
                    close=format_time(close),
                )
            wanted = dt.datetime.combine(frame.date, frame.time)
            window = (frame.time, (wanted + dt.timedelta(minutes=1)).time())
            exact = self.repo.find_free_slots(
                frame.department, frame.date, window, frame.doctor, limit=1
            )
            if exact:
                self._choose(frame, _option(exact[0]))
                return None
            nearest = self.repo.find_nearest_free_slots(
                frame.department, wanted, doctor=frame.doctor
            )
            return self._offer(frame, nearest, self.say("slot_taken", when=format_slot(wanted)))

        tod = frame.time_of_day
        window = (tod.start, tod.end) if tod else None
        slots = self.repo.find_free_slots(frame.department, frame.date, window, frame.doctor)
        if slots:
            return self._offer(frame, slots)
        when = (
            f"{tod.label} on {format_date(frame.date)}" if tod else f"on {format_date(frame.date)}"
        )
        if frame.doctor:
            when += f" with {frame.doctor}"
        around = dt.datetime.combine(frame.date, window[0] if window else dt.time(9))
        nearest = self.repo.find_nearest_free_slots(frame.department, around, doctor=frame.doctor)
        return self._offer(frame, nearest, self.say("nothing_free_then", when=when))

    def _offer(self, frame: Frame, slots: list[Slot], intro: str = "") -> str:
        if not slots:
            department = frame.department
            frame.department = frame.doctor = frame.date = frame.time = frame.time_of_day = None
            frame.clear_selection()
            ask = self._ask(frame, "no_slots_at_all", "department", department=department)
            return " ".join(filter(None, [intro, ask]))
        options = [_option(s) for s in slots]
        frame.candidate_slots = options
        frame.chosen_slot = None
        frame.state = State.OFFER_SLOTS
        frame.expected_slot = "time"
        days = {o.start.date() for o in options}
        if len(days) == 1:
            items = [f"{format_time(o.start.time())} with {o.doctor}" for o in options]
            listing = f"on {format_date(options[0].start.date())}: {join_words(items, 'or')}"
        else:
            listing = join_words([f"{format_slot(o.start)} with {o.doctor}" for o in options], "or")
        key = "nearest_instead" if intro else "offer_slots"
        return " ".join(filter(None, [intro, self.say(key, options=listing)]))

    def _details_step(self, frame: Frame) -> str:
        slot = frame.chosen_slot
        if not frame.patient_name:
            when = f"{format_slot(slot.start)} with {slot.doctor}"
            return self._ask(frame, "ask_name", "patient_name", slot=when)
        if not frame.phone:
            return self._ask(frame, "ask_phone", "phone", name=frame.patient_name)
        frame.state = State.CONFIRM
        frame.expected_slot = None
        return self.say(
            "confirm_booking",
            department=slot.department,
            doctor=slot.doctor,
            slot=format_slot(slot.start),
            name=frame.patient_name,
            phone=format_phone(frame.phone),
        )

    def _lookup_step(self, frame: Frame, notes: list[str]) -> str | None:
        """Find the caller's existing booking. Returns a prompt, or None once found."""
        if frame.appointment:
            return None
        if frame.booking_ref:
            appointment = self.repo.get_appointment(ref=frame.booking_ref)
            active = (
                appointment is not None
                and appointment.status == AppointmentStatus.BOOKED
                and appointment.slot.start_time > self.now()
            )
            if not active:
                ref, frame.booking_ref = frame.booking_ref, None
                return self._ask(frame, "ref_not_found", "booking_ref", ref=ref)
        elif frame.phone:
            appointment = self.repo.get_appointment(phone=frame.phone)
            if appointment is None:
                phone, frame.phone = frame.phone, None
                return self._ask(frame, "phone_not_found", "booking_ref", phone=format_phone(phone))
        else:
            return self._ask(frame, "ask_booking_ref", "booking_ref")

        slot = appointment.slot
        frame.appointment = FoundAppointment(
            booking_ref=appointment.booking_ref,
            slot_id=slot.id,
            start=slot.start_time,
            doctor=slot.doctor.name,
            department=slot.doctor.department.name,
            patient_name=appointment.patient.name,
        )
        frame.booking_ref = appointment.booking_ref
        if frame.task == "reschedule":
            frame.department = frame.appointment.department
            frame.doctor = frame.doctor or frame.appointment.doctor
            notes.append(
                self.say(
                    "found_for_reschedule",
                    department=frame.appointment.department,
                    doctor=frame.appointment.doctor,
                    slot=format_slot(frame.appointment.start),
                )
            )
        return None

    def _confirm_reschedule(self, frame: Frame) -> str:
        frame.state = State.CONFIRM
        frame.expected_slot = None
        return self.say(
            "confirm_reschedule",
            department=frame.appointment.department,
            old=format_slot(frame.appointment.start),
            new=format_slot(frame.chosen_slot.start),
            doctor=frame.chosen_slot.doctor,
        )

    def _confirm_cancel(self, frame: Frame) -> str:
        frame.state = State.CONFIRM
        frame.expected_slot = None
        appointment = frame.appointment
        return self.say(
            "confirm_cancel",
            department=appointment.department,
            doctor=appointment.doctor,
            slot=format_slot(appointment.start),
            name=appointment.patient_name,
        )

    # --- confirmation & side effects -----------------------------------------

    def _at_confirm(self, nlu: NLUResult, frame: Frame) -> Decision:
        intent = nlu.intent
        if intent == "affirm" or TASK_INTENTS.get(intent) == frame.task:
            return self._execute(frame)
        if intent == "deny":
            if frame.task == "cancel":
                frame.reset_task()
                frame.state = State.DONE
                text = f"{self.say('cancel_kept')} {self.say('anything_else')}"
                return self._reply(frame, text, action="cancel_declined")
            frame.state = State.COLLECT_SLOTS
            frame.expected_slot = CHANGE_WHICH
            return self._reply(frame, self.say("what_to_change"))
        if intent == "change_request" and self._clear_named_field(nlu, frame):
            return self._advance(frame, [])
        return self._not_understood(frame, nlu, self.say("yes_or_no"))

    def _execute(self, frame: Frame) -> Decision:
        try:
            if frame.task == "book":
                slot = frame.chosen_slot
                booked = self.repo.book_slot(slot.slot_id, frame.patient_name, frame.phone)
                frame.booking_ref = booked.booking_ref
                text = self.say(
                    "booked",
                    doctor=slot.doctor,
                    slot=format_slot(slot.start),
                    ref=spell_ref(booked.booking_ref),
                    name=frame.patient_name,
                )
                action = "booked"
            elif frame.task == "reschedule":
                slot = frame.chosen_slot
                moved = self.repo.reschedule_appointment(
                    frame.appointment.booking_ref, slot.slot_id
                )
                text = self.say(
                    "rescheduled",
                    slot=format_slot(slot.start),
                    doctor=slot.doctor,
                    ref=spell_ref(moved.booking_ref),
                )
                action = "rescheduled"
            else:
                self.repo.cancel_appointment(frame.appointment.booking_ref)
                text = self.say("cancelled", slot=format_slot(frame.appointment.start))
                action = "cancelled"
        except SlotUnavailableError:
            # Lost a race for the slot: offer the nearest free ones instead.
            taken = frame.chosen_slot
            frame.chosen_slot = None
            nearest = self.repo.find_nearest_free_slots(
                taken.department, taken.start, doctor=frame.doctor
            )
            text = self._offer(frame, nearest, self.say("slot_just_taken"))
            return self._reply(frame, text, action="slot_unavailable")
        except AppointmentNotFoundError:
            ref = frame.appointment.booking_ref
            frame.appointment = None
            frame.booking_ref = None
            return self._reply(frame, self._ask(frame, "ref_not_found", "booking_ref", ref=ref))

        frame.task = None
        frame.state = State.DONE
        frame.expected_slot = None
        return self._reply(frame, f"{text} {self.say('anything_else')}", action=action)

    # --- small talk, info, failures ----------------------------------------

    def _answer_info(self, intent: str, e: Entities, frame: Frame) -> Decision:
        if intent == "clinic_hours":
            text = opening_hours_text()
        elif intent == "clinic_location":
            text = self.say("location")
        elif intent == "list_departments":
            text = self.say("departments", departments=join_words(self.repo.department_names()))
            if e.unknown_department:
                text = f"{self.say('unknown_department', name=e.unknown_department)} {text}"
        else:
            department = e.department or frame.department
            grouped = self.repo.doctors_by_department(department)
            if department and grouped.get(department):
                doctors = join_words(grouped[department])
                text = self.say("doctors_in", department=department, doctors=doctors)
            else:
                grouped = self.repo.doctors_by_department()
                listing = "; ".join(f"{d}: {join_words(names)}" for d, names in grouped.items())
                text = self.say("doctors_all", listing=listing)
        return self._continue(frame, text)

    def _continue(self, frame: Frame, text: str) -> Decision:
        """Say something, then pick the conversation back up where it was."""
        if frame.task and frame.last_prompt:
            return self._reply(frame, f"{text} {frame.last_prompt}", remember=False)
        return self._reply(frame, f"{text} {self.say('anything_else')}")

    def _not_understood(self, frame: Frame, nlu: NLUResult, message: str | None = None) -> Decision:
        frame.fail_count += 1
        if frame.fail_count >= MAX_FAILURES:
            return self._handoff(frame, "handoff_failures")
        digits = re.sub(r"\D", "", nlu.normalized_text)
        if frame.expected_slot == "phone" and len(digits) >= 3:
            text = self.say("invalid_phone")
        else:
            text = f"{message or self.say('not_understood')} {frame.last_prompt}".strip()
        return self._reply(frame, text, action="not_understood", remember=False)

    def _silence(self, frame: Frame) -> Decision:
        frame.silence_count += 1
        if frame.silence_count >= MAX_SILENCES:
            frame.state = State.END
            frame.expected_slot = None
            return self._reply(
                frame, self.say("silence_end"), action="ended_silence", end_call=True
            )
        text = f"{self.say('silence')} {frame.last_prompt}".strip()
        return self._reply(frame, text, action="silence", remember=False)

    def _handoff(self, frame: Frame, key: str) -> Decision:
        frame.state = State.HANDOFF
        frame.expected_slot = None
        return self._reply(frame, self.say(key), action="handoff", end_call=True)

    def _reply(
        self,
        frame: Frame,
        text: str,
        *,
        action: str | None = None,
        end_call: bool = False,
        remember: bool = True,
    ) -> Decision:
        if remember:
            frame.last_prompt = text
        return Decision(
            reply_text=text,
            state=frame.state,
            frame=frame.model_copy(deep=True),
            action=action,
            end_call=end_call,
            expected_slot=frame.expected_slot,
        )
