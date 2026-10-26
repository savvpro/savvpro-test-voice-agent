from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend import store
from backend.database import Allocation, Appointment
from backend.domain import describe, from_utc, local_slot, validate_slot
from backend.nlu import parse

WELCOME = "Welcome to Bayline. I can book, reschedule, or cancel a demo service appointment. How can I help?"


def decide(
    db: Session, sid: str, previous: dict[str, Any], text: str, now: datetime
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    state = deepcopy(previous)
    before = state.get("phase", "IDLE")
    p = parse(
        text,
        now,
        awaiting_time=bool(state.get("slots", {}).get("date"))
        and before != "SELECTING_APPOINTMENT"
        and not state.get("alternatives"),
    )
    trace: dict[str, Any] = {
        "from_state": before,
        "intent": p.intent,
        "rules": p.rules,
        "extracted": p.slots.copy(),
        "validation": [],
        "action": "none",
    }

    def say(message: str, action: str = "none") -> tuple[dict[str, Any], str, dict[str, Any]]:
        state["last_reply"] = message
        trace.update(
            to_state=state.get("phase", "IDLE"),
            action=action,
            intent=state.get("intent") if p.intent is None else p.intent,
        )
        return state, message, trace

    if p.intent == "HOURS":
        return say(
            "We open Monday through Saturday, 9 AM to 6 PM Pakistan time. We're closed Sundays. How would you like to continue?"
        )
    if p.intent == "SERVICES":
        return say(
            "We offer oil changes and tyre rotations, each 30 minutes, and brake inspections, 60 minutes, for cars and SUVs. This is a fictional demo with no payments. Which service would you like?"
        )
    if p.intent == "HELP":
        return say(
            "I can book, reschedule, or cancel a service. Try: book an oil change for my car tomorrow at 10 AM. You can also change details before confirming."
        )
    if p.intent == "REPEAT":
        return say(state.get("last_reply", WELCOME))
    if p.intent == "END":
        state = {"phase": "ENDED"}
        return say(
            "Thanks for calling Bayline. Any unconfirmed changes have been discarded. Goodbye.",
            "end_call",
        )
    appointments = store.owned(db, sid, now)
    if p.intent == "LIST":
        if not appointments:
            return say("You have no upcoming active appointments. Would you like to book one?")
        return say(
            "Your upcoming appointments: "
            + "; ".join(
                f"{i + 1}: {store.summary(appt)['description']}"
                for i, appt in enumerate(appointments)
            )
        )

    if (
        p.intent == "CANCEL"
        and state.get("intent") == "BOOK"
        and before in ("COLLECTING", "CONFIRMING")
        and "my appointment" not in text.lower()
        and "my booking" not in text.lower()
    ):
        state = {"phase": "IDLE"}
        return say(
            "I've discarded the unconfirmed booking. Your existing appointments are unchanged. What would you like to do?",
            "discard_draft",
        )
    if p.intent in ("BOOK", "RESCHEDULE", "CANCEL"):
        if p.intent != state.get("intent") or before in ("COMPLETED", "ENDED"):
            state = {"phase": "COLLECTING", "intent": p.intent, "slots": {}}
        elif p.intent in ("RESCHEDULE", "CANCEL") and p.reference:
            state = {"phase": "COLLECTING", "intent": p.intent, "slots": {}}
    elif before in ("COMPLETED", "ENDED"):
        state = {"phase": "IDLE"}
    if p.no:
        state = {"phase": "IDLE"}
        return say(
            "No changes made. Would you like to book, reschedule, or cancel an appointment?",
            "decline",
        )
    if not state.get("intent"):
        if p.slots:
            state = {"phase": "COLLECTING", "intent": "BOOK", "slots": {}}
            trace["rules"].append("details_imply_booking")
        else:
            return say("Would you like to book, reschedule, or cancel a service appointment?")
    if p.issue:
        trace["validation"].append(p.issue)
        return say(p.issue)

    intent = state["intent"]
    prefix = ""
    target: Appointment | None = None
    if intent in ("RESCHEDULE", "CANCEL"):
        if intent == "CANCEL" and before == "CONFIRMING" and p.selection is not None:
            state.pop("target", None)
            state["slots"] = {}
            trace["rules"].append("cancellation_selection_requires_readback")
        if intent == "CANCEL" and state.get("target") and p.slots:
            current_target = next((a for a in appointments if a.id == state["target"]), None)
            if current_target is not None:
                current_details = store.summary(current_target)
                if any(current_details.get(key) != value for key, value in p.slots.items()):
                    state.pop("target", None)
                    state["slots"] = {}
                    trace["rules"].append("cancellation_target_changed")
        if state.get("target"):
            target = next((a for a in appointments if a.id == state["target"]), None)
            if target is None:
                state = {"phase": "IDLE"}
                return say(
                    "That appointment is no longer active. Please choose another appointment."
                )
        if target is None:
            candidates = appointments
            if p.reference:
                candidates = [a for a in candidates if a.id[:8].upper() == p.reference]
            if p.slots.get("service"):
                candidates = [a for a in candidates if a.service == p.slots["service"]]
            if p.slots.get("vehicle"):
                candidates = [a for a in candidates if a.vehicle == p.slots["vehicle"]]
            # A reschedule's date normally names the destination. "appointment on" identifies the source.
            if p.slots.get("date") and (intent == "CANCEL" or "appointment on" in text.lower()):
                candidates = [
                    a for a in candidates if from_utc(a.start).date().isoformat() == p.slots["date"]
                ]
            selected = state.get("candidates", [a.id for a in candidates])
            if before in ("SELECTING_APPOINTMENT", "CONFIRMING") and p.selection is not None:
                try:
                    chosen = selected[p.selection]
                    candidates = [a for a in appointments if a.id == chosen]
                except IndexError:
                    candidates = []
            if not appointments:
                state = {"phase": "IDLE"}
                return say(
                    "No active booking was found for you. Would you like to book a new service?"
                )
            if not candidates:
                state["phase"] = "SELECTING_APPOINTMENT"
                state["candidates"] = [a.id for a in appointments]
                return say("No appointment matched that choice. " + _choices(appointments))
            if len(candidates) > 1:
                state["phase"] = "SELECTING_APPOINTMENT"
                state["candidates"] = [a.id for a in candidates]
                if intent == "RESCHEDULE":
                    state["proposed"] = {k: v for k, v in p.slots.items() if k in ("date", "time")}
                return say(_choices(candidates))
            target = candidates[0]
            detail = store.summary(target)
            state.update(
                target=target.id,
                phase="COLLECTING",
                slots={k: detail[k] for k in ("service", "vehicle", "date", "time")},
            )
            prefix = "I found your " + detail["description"] + ". "
            trace["rules"].append("appointment_selected")
            if intent == "RESCHEDULE":
                state["needs_new_schedule"] = True
                for key, value in state.pop("proposed", {}).items():
                    state["slots"][key] = value
                    state["needs_new_schedule"] = False
        if intent == "CANCEL":
            if (
                before == "CONFIRMING"
                and previous.get("intent") == "CANCEL"
                and target is not None
                and previous.get("target") == target.id
                and p.yes
                and not p.slots
                and p.selection is None
            ):
                assert target is not None
                db.execute(delete(Allocation).where(Allocation.appointment_id == target.id))
                target.status = "cancelled"
                state = {"phase": "COMPLETED", "appointment": store.summary(target)}
                return say(
                    "Your appointment is cancelled and its bay has been released. Is there anything else I can help with?",
                    "cancelled",
                )
            state["phase"] = "CONFIRMING"
            assert target is not None
            return say(
                prefix
                + "Please confirm: cancel your "
                + store.summary(target)["description"]
                + "? Say yes to cancel, or no to keep it."
            )

    slots = state.setdefault("slots", {})
    updates = p.slots.copy()
    # An ordinal chooses a displayed alternative, never an arbitrary time.
    if p.selection is not None and state.get("alternatives") and not updates:
        try:
            choice = state["alternatives"][p.selection]
            updates = {k: choice[k] for k in ("date", "time")}
            trace["rules"].append("alternative_selected")
        except IndexError:
            return say(
                "Please choose one of the displayed alternatives, or tell me another date and time."
            )
    slots.update(updates)
    if updates:
        state["phase"] = "COLLECTING"
        trace["rules"].append("slot_update_invalidates_confirmation")
    if intent == "RESCHEDULE" and ("date" in updates or "time" in updates):
        state["needs_new_schedule"] = False
    if intent == "RESCHEDULE" and state.get("needs_new_schedule"):
        return say(
            prefix
            + "What new date and time would you like? Your current booking stays in place until you confirm."
        )
    questions = {
        "service": "Which service would you like: oil change, tyre rotation, or brake inspection?",
        "vehicle": "Is this for a car or an SUV?",
        "date": "What day would you like?",
        "time": "What time would you prefer, between 9 AM and 6 PM PKT?",
    }
    for key, question in questions.items():
        if not slots.get(key):
            state["phase"] = "COLLECTING"
            return say(prefix + question)
    start = local_slot(slots["date"], slots["time"])
    problem = validate_slot(slots["service"], start, now)
    exclude = target.id if target else None
    if problem or not store.free_bays(db, sid, start, slots["service"], exclude):
        trace["validation"].append(problem or "both_bays_occupied")
        options = store.alternatives(db, sid, start, slots["service"], now, exclude)
        state.update(phase="COLLECTING", alternatives=options)
        slots.pop("time", None)
        if (
            start.weekday() == 6
            or start.date() < now.date()
            or (start.date() - now.date()).days > 14
        ):
            slots.pop("date", None)
        message = problem or "Both service bays are occupied at that time."
        if options:
            message += (
                " Nearby available choices: "
                + "; ".join(f"{i + 1}: {option['label']}" for i, option in enumerate(options))
                + ". Which works for you?"
            )
        return say(message)
    trace["validation"].append("slot_available")
    state.pop("alternatives", None)
    if (
        before == "CONFIRMING"
        and previous.get("intent") == intent
        and previous.get("target") == state.get("target")
        and p.yes
        and not updates
    ):
        appointment = store.reserve(db, sid, slots["service"], slots["vehicle"], start, target)
        if appointment is None:
            state["phase"] = "COLLECTING"
            slots.pop("time", None)
            return say(
                "That slot was just taken. Your existing booking is unchanged. Please choose another time."
            )
        result = store.summary(appointment)
        state = {"phase": "COMPLETED", "appointment": result}
        action = "rescheduled" if intent == "RESCHEDULE" else "booked"
        return say(
            f"You're {action}: {result['description']}. Your demo reference is {result['reference']}. Is there anything else I can help with?",
            action,
        )
    state["phase"] = "CONFIRMING"
    operation = "reschedule to" if intent == "RESCHEDULE" else "book"
    return say(
        prefix
        + f"Please confirm: {operation} {describe(slots['service'], slots['vehicle'], start)}. Say yes to confirm, or tell me what to change."
    )


def _choices(appointments: list[Appointment]) -> str:
    return (
        "Which appointment would you like to change? "
        + "; ".join(
            f"{i + 1}: {store.summary(appt)['description']}" for i, appt in enumerate(appointments)
        )
        + ". Say its number, service, or booking reference."
    )
