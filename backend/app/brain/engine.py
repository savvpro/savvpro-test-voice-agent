"""Explicit conversation transitions. All effects are delegated to BookingPort."""
import re
from datetime import date, datetime
from typing import Protocol

from app.brain.language import Recognition, confirms_action, extract, intent_text, normalize, recognize, schedule_change_field
from app.catalog import ADDRESS_INFO, BUSINESS_INFO, HOURS_INFO, SERVICE_INFO, SERVICES
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
        if not c.last_booking_reference:
            c.last_booking_reference = self.recent_reference(c)
        active = c.current_intent in (Intent.CREATE, Intent.AVAILABILITY, Intent.CANCEL, Intent.RESCHEDULE) and c.state not in (State.COMPLETED, State.BOOKED)
        recognition = recognize(text, active)
        parsed = extract(text, self.now,
                         expecting_name=active and c.missing_information == ["name"] and recognition.intent == Intent.UNKNOWN,
                         expecting_time=active and "time" in c.missing_information,
                         expecting_date=active and "date" in c.missing_information,
                         rescheduling=recognition.intent == Intent.RESCHEDULE or (active and c.current_intent == Intent.RESCHEDULE))
        found = parsed.entities.model_dump(exclude_none=True)
        used_context_reference = False
        c.history.append(Message(role="user", text=text))
        c.revision += 1

        def finish(reply: str, rule: str, action: str, explanation: str, *, clarify: bool = False) -> SessionView:
            if used_context_reference:
                explanation += " Reused the last verified booking reference from this session; no reference was guessed from a name or another session."
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
            c.rejected_fields = []
            c.current_intent = Intent.UNKNOWN
            c.state = State.IDLE

        if intent_text(text) in ("start over", "restart", "restart conversation"):
            reset()
            return finish("Let's start over. Would you like to book, check availability, reschedule, or cancel?", "control.restart", "ask_intent", "Discarded the uncommitted proposal; existing appointments remain stored.")
        if recognition.intent == Intent.END:
            c.state = State.COMPLETED
            c.proposed_action = None
            c.missing_information = []
            return finish("Thanks for calling Northline Studio. Goodbye!", recognition.rule, "end", "Ended without applying any pending changes.")
        if recognition.intent == Intent.REPEAT:
            return finish(c.reply, recognition.rule, "repeat", "Repeated the previous reply without changing the proposal.")
        if recognition.rule == "control.thanks":
            reply = "You're welcome. " + (self.prompt(c) if active else "Is there anything else I can help with?")
            return finish(reply, recognition.rule, "acknowledge", "Acknowledged courtesy without ending the workflow, changing its details or authorizing a write.")
        if recognition.rule == "booking.reference_help":
            if c.last_booking_reference:
                try:
                    appointment = self.bookings.lookup(c.last_booking_reference)
                except BookingError:
                    c.last_booking_reference = None
                else:
                    if c.state == State.IDENTIFYING and c.current_intent in (Intent.RESCHEDULE, Intent.CANCEL):
                        # Also recovers sessions persisted by older versions that
                        # discarded the reference when changing workflow.
                        c.entities.reference = appointment.reference
                        recognition = Recognition(c.current_intent, "context.reference_recovered")
                        used_context_reference = True
                    else:
                        suffix = " " + self.prompt(c) if active else " You can say 'reschedule it to 5 PM' or 'cancel it'."
                        return finish(f"Your booking reference is {appointment.reference}. It is on your booking receipt and in this conversation. You don't need to copy it to change this booking here." + suffix, recognition.rule, "show_reference", "Retrieved the session's known reference from the database without changing any appointment.")
            if recognition.rule == "booking.reference_help":
                return finish("Look for NL- followed by eight letters or digits on your booking receipt or in the earlier confirmation message. I don't have a verified booking reference in this session. Please paste it here to find an existing appointment.", recognition.rule, "explain_reference", "No verified reference was available in this session; did not search other customers or guess an appointment.", clarify=True)
        if recognition.rule == "booking.status_question":
            if active and c.current_intent == Intent.CREATE:
                reply = "Not yet. Your appointment has not been booked. " + self.prompt(c)
            elif c.current_intent == Intent.AVAILABILITY:
                reply = "Not yet. I checked availability, but haven't made a new booking from those results. " + (self.availability_prompt(c) if c.available_slots else self.prompt(c))
            elif c.proposed_action:
                reply = f"Not yet. The proposed {c.proposed_action} has not been applied. " + self.prompt(c)
            elif c.last_booking_reference:
                try:
                    appointment = self.bookings.lookup(c.last_booking_reference)
                    reply = f"Your appointment is {appointment.status}. Reference {appointment.reference}: {appointment.service_name} on {appointment.starts_at[:10]} at {appointment.starts_at[11:16]} (studio time)."
                except BookingError as error:
                    reply = str(error)
            else:
                reply = "I haven't booked an appointment in this session. " + self.prompt(c)
            return finish(reply, recognition.rule, "show_booking_status", "Answered from the pending proposal or database record; a status question never authorizes a write.")
        if recognition.intent == Intent.INFO:
            reply = self.business_reply(text)
            if active:
                reply += " Your current request is saved. " + self.prompt(c)
            return finish(reply, recognition.rule, "answer_question", "Answered from the static business catalog and preserved conversation context.")
        if recognition.rule == "action.multiple_requests":
            c.proposed_action = None
            if c.state == State.CONFIRMING:
                c.state = State.RESCHEDULING if c.current_intent == Intent.RESCHEDULE else State.COLLECTING
            return finish("Please choose one action: book, check availability, reschedule, or cancel.", recognition.rule, "clarify_intent", "Multiple requested actions cannot safely share a confirmation.", clarify=True)
        saved_target = parsed.entities.reference or re.search(r"\b(?:existing|confirmed|original|previous) (?:booking|appointment)\b", intent_text(text))
        cancel_draft = recognition.intent == Intent.CANCEL and active and c.current_intent in (Intent.CREATE, Intent.AVAILABILITY) and not saved_target
        if recognition.intent == Intent.DENY or cancel_draft:
            had_pending = active or bool(c.proposed_action)
            saved_appointment = c.appointment if not active or c.current_intent in (Intent.RESCHEDULE, Intent.CANCEL) else None
            reset()
            c.appointment = saved_appointment
            if not had_pending:
                return finish("There is no pending request to discard. Existing appointments are unchanged. Is there anything else I can help with?", recognition.rule, "ask_intent", "No pending proposal existed; preserved the saved receipt and made no calendar changes.")
            return finish("I discarded the pending request. Existing appointments are unchanged. What would you like to do next?", recognition.rule, "ask_intent", "Discarded only the uncommitted proposal; no persisted appointment was changed.")
        if recognition.intent == Intent.CANCEL and active and c.current_intent == Intent.RESCHEDULE and not saved_target and re.fullmatch(r"(?:please )?cancel(?: it| this| that)?", intent_text(text)):
            c.proposed_action = None
            c.state = State.RESCHEDULING
            return finish("Do you want to discard this change or cancel your confirmed appointment? Say 'discard the change' or 'cancel my confirmed appointment'.", "cancel.target_ambiguous", "clarify_cancel_target", "An ambiguous pronoun cannot select a destructive target or retain prior authorization.", clarify=True)

        if active and re.fullmatch(r"(?:i (?:just|already) told you (?:the|my) name|i already gave you my name)(?: bro)?", normalize(text)):
            if c.entities.name:
                reply = f"I have the name {c.entities.name} for this request. " + self.prompt(c)
            else:
                reply = "I don't have a name saved for this request. Please say 'use the name' followed by a fictional name."
            return finish(reply, "context.name_reminder", "show_name", "Answered using only the current draft's stored name; did not guess, change the proposal or write a booking.")

        availability_result = c.current_intent == Intent.AVAILABILITY and c.state == State.COMPLETED and bool(c.available_slots)
        accept_offer = recognition.intent == Intent.CONFIRM and availability_result
        accept_with_details = recognition.rule == "confirmation.with_details" and bool(found or parsed.issues)
        if c.current_intent == Intent.AVAILABILITY and (accept_offer or accept_with_details):
            # "Yes, do it at 4:30 PM" accepts the booking offer and contributes
            # its selected time; it never bypasses review/confirmation.
            recognition = Recognition(Intent.CREATE, "context.accept_available_slot")
        elif availability_result and recognition.intent in (Intent.UNKNOWN, Intent.MODIFY) and (found or parsed.issues):
            # A date/time answer after a completed availability query is still
            # part of that query. Merge and recheck it rather than discarding it.
            active = True
        if recognition.intent == Intent.RESCHEDULE and active and c.current_intent in (Intent.CREATE, Intent.AVAILABILITY) and not parsed.entities.reference:
            recognition = Recognition(Intent.MODIFY, "context.draft_correction")
        if c.state == State.CONFIRMING and c.proposed_action and not found and not parsed.issues and recognition.intent == c.current_intent and confirms_action(text, c.current_intent):
            recognition = Recognition(Intent.CONFIRM, "confirmation.explicit_action")

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
                    if error.field not in c.rejected_fields:
                        c.rejected_fields.append(error.field)
                    c.state = State.RESCHEDULING if c.current_intent == Intent.RESCHEDULE else State.COLLECTING
                    c.missing_information = [error.field]
                return finish(str(error) + " " + self.prompt(c), "commit.rejected", "clarify", "Revalidated at commit; rejected the action without claiming success.", clarify=True)
            c.last_committed_action = c.proposed_action
            c.last_booking_reference = c.appointment.reference
            c.proposed_action = None
            c.missing_information = []
            return finish(f"{verb}. Reference {c.appointment.reference}. " + self.describe(c.entities) + ". Please keep your reference.", "commit.confirmed", "show_receipt", "Explicit confirmation authorized the database operation; the API returns only after the transaction commits.")

        action_intents = (Intent.CREATE, Intent.AVAILABILITY, Intent.CANCEL, Intent.RESCHEDULE)
        if recognition.intent in action_intents and (not active or recognition.intent != c.current_intent):
            # Turning an availability result into a booking retains the queried details.
            carry_details = (c.current_intent == Intent.AVAILABILITY and recognition.intent == Intent.CREATE and (active or c.state == State.COMPLETED)) or (c.current_intent == Intent.CREATE and recognition.intent == Intent.AVAILABILITY and active)
            carry = c.entities.model_copy(deep=True) if carry_details else None
            reference = c.last_booking_reference if recognition.intent in (Intent.RESCHEDULE, Intent.CANCEL) and not parsed.entities.reference else None
            reset()
            if carry:
                c.entities = carry
            c.current_intent = recognition.intent
            if reference:
                c.entities.reference = reference
                used_context_reference = True
            active = True
        if not active:
            if c.current_intent == Intent.AVAILABILITY and c.state == State.COMPLETED and c.available_slots:
                return finish(self.availability_prompt(c), "recovery.availability_followup", "clarify_booking_offer", "Kept the checked slot after an unclear transcript. Did not fuzzy-match the speech to an action or write a booking.", clarify=True)
            return finish("I can book a haircut or beard trim, check availability, reschedule, cancel, or explain our services. Which would you like?", "fallback.unknown", "ask_intent", "No supported active task was identified; no action taken.", clarify=True)

        # Fresh entities override only their own fields. Every correction clears authorization.
        changed = bool(found or parsed.issues)
        if changed:
            c.proposed_action = None
            c.available_slots = []
            for key, value in found.items():
                setattr(c.entities, key, value)
                if key in c.rejected_fields:
                    c.rejected_fields.remove(key)
            for key in parsed.issues:
                setattr(c.entities, key, None)
                if key not in c.rejected_fields:
                    c.rejected_fields.append(key)
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
            c.last_booking_reference = appointment.reference
            if fresh_target:
                c.appointment = appointment
                c.target_version = appointment.version
                c.entities.name = appointment.customer_name
                if c.current_intent == Intent.RESCHEDULE and "service" not in c.rejected_fields:
                    c.entities.service = c.entities.service or appointment.service
            elif appointment.version != c.target_version:
                c.appointment = appointment
                c.target_version = appointment.version
                c.proposed_action = None
            if c.current_intent == Intent.RESCHEDULE:
                if recognition.rule == "action.reschedule" and not parsed.issues and not any(key in found for key in ("date", "time", "period", "service", "name")):
                    # An explicit request without a destination opens collection;
                    # it must not re-propose values from an earlier ready change.
                    c.proposed_action = None
                    c.entities.date = None
                    c.entities.time = None
                    c.entities.period = None
                    focus = schedule_change_field(text)
                    c.missing_information = [focus] if focus else ["date", "time"]
                    if focus == "time" and "date" not in c.rejected_fields:
                        c.entities.date = appointment.starts_at[:10]
                    elif focus == "date" and "time" not in c.rejected_fields:
                        c.entities.time = appointment.starts_at[11:16]
                open_schedule_question = c.missing_information == ["date", "time"] and not c.rejected_fields
                if c.entities.time and not c.entities.date and "date" not in parsed.issues and "date" not in c.rejected_fields and ("date" not in c.missing_information or open_schedule_question):
                    c.entities.date = appointment.starts_at[:10]
                elif c.entities.date and not c.entities.time and not c.entities.period and "time" not in parsed.issues and "time" not in c.rejected_fields and ("time" not in c.missing_information or open_schedule_question):
                    c.entities.time = appointment.starts_at[11:16]
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
            c.missing_information = list(c.rejected_fields)
            return finish(next(iter(parsed.issues.values())), "entities.ambiguous", "clarify_entities", "Ambiguous or unsupported values were cleared; all other known fields were retained.", clarify=True)

        if c.entities.date:
            try:
                self.bookings.day(c.entities.date)
            except BookingError as error:
                c.entities.date = None
                if "date" not in c.rejected_fields:
                    c.rejected_fields.append("date")
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
                reply = "Available starts: " + ", ".join(c.available_slots[:8]) + ". Would you like to book?" if c.available_slots else "There are no available starts for that date and period. Try another date."
                if not c.available_slots:
                    c.entities.date = None
                    c.missing_information = ["date"]
                return finish(reply, "availability.real_slots", "show_availability", "Computed duration-aware slots from operating hours and stored appointments; no reservation made.")
            self.bookings.check(c.entities, excluding)
        except BookingError as error:
            setattr(c.entities, error.field, None)
            if error.field not in c.rejected_fields:
                c.rejected_fields.append(error.field)
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
    def business_reply(text: str) -> str:
        """Select brief catalog answers instead of reading every business fact."""
        t = normalize(text)
        if re.search(r"\bhow (?:(?:do|can|could) i |to )(?:cancel|reschedule|change|adjust|update|shift)\b", t):
            return "Tell me to reschedule or cancel your appointment. I can use the booking we discussed here; for another booking, give its NL reference. I'll ask you to confirm the change first."
        if re.search(r"\bhow (?:(?:do|can) i |to )(?:book|make)\b", t):
            return "Tell me which service, day, and time you want. I'll check the slot, ask your name, and have you confirm before booking."
        parts = []
        if re.search(r"\b(?:services|offer|prices?|cost|how much)\b", t):
            parts.append(SERVICE_INFO)
        if re.search(r"\b(?:hours|open|close)\b", t):
            parts.append(HOURS_INFO)
        if re.search(r"\b(?:address|where are you)\b", t):
            parts.append(ADDRESS_INFO)
        return " ".join(parts) or BUSINESS_INFO

    @staticmethod
    def recent_reference(c: SessionView) -> str | None:
        """Recover old session payloads using only their own authoritative output."""
        if c.appointment:
            return c.appointment.reference
        for message in reversed(c.history):
            if message.role == "assistant":
                receipt = re.match(r"^(?:Booked|Rescheduled|Cancelled)\. Reference (NL-[A-Z0-9]{8})\.", message.text)
                if receipt:
                    return receipt[1]
        return None

    @staticmethod
    def availability_prompt(c: SessionView) -> str:
        service = SERVICES[c.entities.service].name if c.entities.service in SERVICES else "that service"
        when = f" on {c.entities.date}" if c.entities.date else ""
        when += f" at {c.entities.time}" if c.entities.time else ""
        return f"I still have availability for {service}{when}. Did you want to book? Say 'book it' or 'yes' to continue; nothing has been booked yet."

    @staticmethod
    def describe(entities: Entities) -> str:
        service = SERVICES[entities.service].name if entities.service in SERVICES else "appointment"
        return f"{service} for {entities.name or 'the customer'} on {entities.date} at {entities.time} (studio time)"

    @staticmethod
    def prompt(c: SessionView) -> str:
        if c.current_intent == Intent.RESCHEDULE and c.missing_information == ["date", "time"] and not c.rejected_fields:
            return "What new date or time would you like? Say a date, a full time such as 5 PM, or both; I'll keep the other saved detail."
        prompts = {"service": "Would you like a Classic Haircut, Beard Trim, or Haircut + Beard?",
                   "date": "Which date? You can say tomorrow, next Monday, or a calendar date such as October 28 2026.",
                   "time": "What time, including AM or PM?", "name": "What fictional name should I use?",
                   "reference": "What is the NL booking reference?"}
        if c.missing_information:
            return prompts[c.missing_information[0]]
        if c.state == State.CONFIRMING:
            return "Say yes to confirm, no to discard, or tell me what to change."
        return "Would you like to book, check availability, reschedule, or cancel?"
