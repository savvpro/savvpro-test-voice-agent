"""Explicit conversation transitions. All effects are delegated to BookingPort."""
from datetime import date, datetime
from typing import Protocol

from app.brain.language import extract, normalize, recognize
from app.catalog import BUSINESS_INFO, SERVICES
from app.schemas import AppointmentView, Decision, Entities, Intent, Message, SessionView, State


class BookingError(Exception):
    def __init__(self, message: str, field: str = "time"):
        super().__init__(message)
        self.field = field


class BookingPort(Protocol):
    def day(self, value: str | None) -> date: ...
    def lookup(self, reference: str) -> AppointmentView: ...
    def check(self, entities: Entities, excluding: str | None = None) -> None: ...
    def slots(self, entities: Entities, excluding: str | None = None) -> list[str]: ...
    def create(self, entities: Entities) -> AppointmentView: ...
    def reschedule(self, entities: Entities, version: int) -> AppointmentView: ...
    def cancel(self, reference: str, version: int) -> AppointmentView: ...


class Engine:
    def __init__(self, bookings: BookingPort, now: datetime):
        self.bookings = bookings
        self.now = now

    def turn(self, context: SessionView, text: str) -> SessionView:
        c = context.model_copy(deep=True)
        previous = c.state
        active = c.current_intent in (Intent.CREATE, Intent.AVAILABILITY, Intent.CANCEL, Intent.RESCHEDULE) and c.state not in (State.COMPLETED, State.BOOKED)
        recognition = recognize(text, active)
        parsed = extract(text, self.now,
                         expecting_name=active and c.missing_information == ["name"],
                         expecting_time=active and "time" in c.missing_information)
        found = parsed.entities.model_dump(exclude_none=True)
        c.history.append(Message(role="user", text=text))
        c.revision += 1

        def finish(reply: str, rule: str, action: str, explanation: str, *, clarify: bool = False) -> SessionView:
            c.reply = reply
            if clarify:
                c.clarification_count += 1
                if c.clarification_count % 3 == 0:
                    c.reply += " You can also say start over or end the conversation."
            else:
                c.clarification_count = 0
            c.last_decision = Decision(
                intent=recognition.intent, extracted_entities=found, previous_state=previous,
                current_state=c.state, matched_rule=rule, explanation=explanation,
                next_action=action, missing_information=c.missing_information,
            )
            c.history.append(Message(role="assistant", text=c.reply))
            # Bound stored history; the last 100 messages are enough for this local demo.
            c.history = c.history[-100:]
            return c

        def reset() -> None:
            c.entities = Entities()
            c.appointment = None
            c.target_version = None
            c.proposed_action = None
            c.last_committed_action = None
            c.available_slots = []
            c.missing_information = []
            c.current_intent = Intent.UNKNOWN
            c.state = State.IDLE

        if normalize(text) in ("start over", "restart", "restart conversation"):
            reset()
            return finish("Let's start over. Would you like to book, check availability, reschedule, or cancel?", "control.restart", "ask_intent", "Discarded the uncommitted proposal; existing appointments remain stored.")
        if recognition.intent == Intent.END:
            c.state = State.COMPLETED
            c.proposed_action = None
            c.missing_information = []
            return finish("Thanks for calling Northline Studio. Goodbye!", recognition.rule, "end", "Ended without applying any pending changes.")
        if recognition.intent == Intent.REPEAT:
            return finish(c.reply, recognition.rule, "repeat", "Repeated the previous reply without changing the proposal.")
        if recognition.intent == Intent.INFO:
            reply = BUSINESS_INFO
            if "how" in normalize(text) and ("cancel" in normalize(text) or "reschedule" in normalize(text)):
                reply += " To change or cancel a booking, give its NL booking reference. I will ask for confirmation first."
            if active:
                reply += " Your current request is saved. " + self.prompt(c)
            return finish(reply, recognition.rule, "answer_question", "Answered from the static business catalog and preserved conversation context.")
        if recognition.rule == "action.multiple_requests":
            return finish("Please choose one action: book, check availability, reschedule, or cancel.", recognition.rule, "clarify_intent", "Multiple requested actions cannot safely share a confirmation.", clarify=True)
        if recognition.intent == Intent.DENY:
            reset()
            return finish("I haven't made any changes. What would you like to do next?", recognition.rule, "ask_intent", "Declined or negated the proposed action; nothing was written.")

        if recognition.intent == Intent.CONFIRM and not found and not parsed.issues:
            if c.state != State.CONFIRMING or not c.proposed_action:
                return finish("There is no action ready to confirm. " + self.prompt(c), "confirmation.no_proposal", "clarify", "Confirmation is valid only after a complete proposal.", clarify=True)
            try:
                if c.current_intent == Intent.CREATE:
                    c.appointment = self.bookings.create(c.entities)
                    c.state = State.BOOKED
                    verb = "Booked"
                elif c.current_intent == Intent.RESCHEDULE:
                    c.appointment = self.bookings.reschedule(c.entities, c.target_version)
                    c.state = State.COMPLETED
                    verb = "Rescheduled"
                elif c.current_intent == Intent.CANCEL:
                    c.appointment = self.bookings.cancel(c.entities.reference, c.target_version)
                    c.state = State.COMPLETED
                    verb = "Cancelled"
                else:
                    raise BookingError("There is no supported action to confirm.")
            except BookingError as error:
                c.proposed_action = None
                if error.field == "reference":
                    c.entities.reference = None
                    c.target_version = None
                    c.appointment = None
                    c.state = State.IDENTIFYING
                    c.missing_information = ["reference"]
                else:
                    setattr(c.entities, error.field, None)
                    c.state = State.RESCHEDULING if c.current_intent == Intent.RESCHEDULE else State.COLLECTING
                    c.missing_information = [error.field]
                return finish(str(error) + " " + self.prompt(c), "commit.rejected", "clarify", "Revalidated at commit; rejected the action without claiming success.", clarify=True)
            c.last_committed_action = c.proposed_action
            c.proposed_action = None
            c.missing_information = []
            return finish(f"{verb}. Reference {c.appointment.reference}. " + self.describe(c.entities) + ". Please keep your reference.", "commit.confirmed", "show_receipt", "Explicit confirmation authorized the database operation; the API returns only after the transaction commits.")

        action_intents = (Intent.CREATE, Intent.AVAILABILITY, Intent.CANCEL, Intent.RESCHEDULE)
        if recognition.intent in action_intents and (not active or recognition.intent != c.current_intent):
            # Turning an availability result into a booking retains the queried details.
            carry = c.entities.model_copy(deep=True) if c.current_intent == Intent.AVAILABILITY and recognition.intent == Intent.CREATE and c.state == State.COMPLETED else None
            reset()
            if carry:
                c.entities = carry
            c.current_intent = recognition.intent
            active = True
        if not active:
            return finish("I can book a haircut or beard trim, check availability, reschedule, cancel, or explain our services. Which would you like?", "fallback.unknown", "ask_intent", "No supported active task was identified; no action taken.", clarify=True)

        # Fresh entities override only their own fields. Every correction clears authorization.
        changed = bool(found or parsed.issues)
        if changed:
            c.proposed_action = None
            c.available_slots = []
            for key, value in found.items():
                setattr(c.entities, key, value)
            for key in parsed.issues:
                setattr(c.entities, key, None)
            if "time" in found:
                c.entities.period = None
            elif "period" in found and c.current_intent != Intent.AVAILABILITY:
                c.entities.time = None
        elif recognition.intent not in action_intents:
            if recognition.intent == Intent.MODIFY:
                c.proposed_action = None
                c.state = State.RESCHEDULING if c.current_intent == Intent.RESCHEDULE else State.COLLECTING
                return finish("What should I change? Please give a service, a date such as Friday, or a time such as 5 PM.", "correction.unspecified", "clarify_change", "An unparsed correction invalidated the previous authorization; no action can be confirmed yet.", clarify=True)
            return finish("I didn't understand that detail. " + self.prompt(c), "fallback.context_unknown", "clarify", "Kept known entities and asked for the outstanding detail.", clarify=True)

        if c.current_intent in (Intent.CANCEL, Intent.RESCHEDULE):
            if not c.entities.reference:
                c.state = State.IDENTIFYING
                c.missing_information = ["reference"]
                return finish("What is the booking reference? It looks like NL- followed by eight letters or digits.", "existing.reference_required", "ask_reference", "Existing appointments are identified by synthetic reference, never by guessing a name.")
            try:
                appointment = self.bookings.lookup(c.entities.reference)
                if appointment.status != "confirmed":
                    raise BookingError("That appointment is already cancelled.", "reference")
            except BookingError as error:
                c.entities.reference = None
                c.state = State.IDENTIFYING
                c.missing_information = ["reference"]
                return finish(str(error) + " Please check the reference.", "existing.not_found", "ask_reference", "No active appointment matched the supplied reference.", clarify=True)
            fresh_target = c.appointment is None or c.appointment.reference != appointment.reference
            if fresh_target:
                c.appointment = appointment
                c.target_version = appointment.version
                c.entities.name = appointment.customer_name
                if c.current_intent == Intent.RESCHEDULE:
                    c.entities.service = c.entities.service or appointment.service
            elif appointment.version != c.target_version:
                c.appointment = appointment
                c.target_version = appointment.version
                c.proposed_action = None
            if c.current_intent == Intent.CANCEL:
                c.entities.service = appointment.service
                c.entities.date = appointment.starts_at[:10]
                c.entities.time = appointment.starts_at[11:16]
                c.entities.name = appointment.customer_name
                c.state = State.CONFIRMING
                c.missing_information = []
                c.proposed_action = "cancel"
                return finish(f"Cancel {appointment.reference}: {self.describe(c.entities)}? Say yes to cancel, or no to keep it.", "cancel.propose", "request_confirmation", "Loaded an active booking; cancellation requires a separate explicit confirmation.")

        if parsed.issues:
            c.state = State.RESCHEDULING if c.current_intent == Intent.RESCHEDULE else State.COLLECTING
            c.missing_information = list(parsed.issues)
            return finish(next(iter(parsed.issues.values())), "entities.ambiguous", "clarify_entities", "Ambiguous or unsupported values were cleared; all other known fields were retained.", clarify=True)

        if c.entities.date:
            try:
                self.bookings.day(c.entities.date)
            except BookingError as error:
                c.entities.date = None
                c.state = State.RESCHEDULING if c.current_intent == Intent.RESCHEDULE else State.COLLECTING
                c.missing_information = ["date"]
                return finish(str(error) + " " + self.prompt(c), "date.rejected", "ask_date", "Rejected an invalid business date before requesting additional details.", clarify=True)

        required = ["service", "date"]
        if c.current_intent != Intent.AVAILABILITY:
            required.append("time")
        c.missing_information = [key for key in required if not getattr(c.entities, key)]
        if c.missing_information:
            c.state = State.RESCHEDULING if c.current_intent == Intent.RESCHEDULE else State.COLLECTING
            return finish(self.prompt(c), "details.missing", "ask_" + c.missing_information[0], "Collected available entities and requested the first required missing value.")

        excluding = c.entities.reference if c.current_intent == Intent.RESCHEDULE else None
        try:
            if c.current_intent == Intent.AVAILABILITY:
                c.available_slots = self.bookings.slots(c.entities)
                c.state = State.COMPLETED if c.available_slots else State.COLLECTING
                reply = "Available starts: " + ", ".join(c.available_slots[:8]) + ". Say book to begin a booking." if c.available_slots else "There are no available starts for that date and period. Try another date."
                if not c.available_slots:
                    c.entities.date = None
                    c.missing_information = ["date"]
                return finish(reply, "availability.real_slots", "show_availability", "Computed duration-aware slots from operating hours and stored appointments; no reservation made.")
            self.bookings.check(c.entities, excluding)
        except BookingError as error:
            setattr(c.entities, error.field, None)
            c.state = State.RESCHEDULING if c.current_intent == Intent.RESCHEDULE else State.COLLECTING
            c.missing_information = [error.field]
            return finish(str(error) + " " + self.prompt(c), "availability.rejected", "ask_" + error.field, "Validated business hours, date, duration and persisted conflicts before proposing an action.", clarify=True)

        if not c.entities.name:
            c.state = State.COLLECTING
            c.missing_information = ["name"]
            return finish("That slot is available. What name should I use? Please use a fictional name for this demo.", "details.name_required", "ask_name", "Availability is valid now; customer name is still required and no appointment has been created.")
        c.state = State.CONFIRMING
        c.missing_information = []
        c.proposed_action = "reschedule" if c.current_intent == Intent.RESCHEDULE else "create"
        return finish(f"{'Reschedule to' if c.current_intent == Intent.RESCHEDULE else 'Book'} {self.describe(c.entities)}? Say yes to confirm, or no to discard.", "proposal.ready", "request_confirmation", "All required details are present and availability was checked again. A later explicit confirmation is required.")

    @staticmethod
    def describe(entities: Entities) -> str:
        service = SERVICES[entities.service].name if entities.service in SERVICES else "appointment"
        return f"{service} for {entities.name or 'the customer'} on {entities.date} at {entities.time} (studio time)"

    @staticmethod
    def prompt(c: SessionView) -> str:
        prompts = {"service": "Would you like a Classic Haircut, Beard Trim, or Haircut + Beard?",
                   "date": "Which date? You can say tomorrow, next Monday, or YYYY-MM-DD.",
                   "time": "What time, including AM or PM?", "name": "What fictional name should I use?",
                   "reference": "What is the NL booking reference?"}
        if c.missing_information:
            return prompts[c.missing_information[0]]
        if c.state == State.CONFIRMING:
            return "Say yes to confirm, no to discard, or tell me what to change."
        return "Would you like to book, check availability, reschedule, or cancel?"
