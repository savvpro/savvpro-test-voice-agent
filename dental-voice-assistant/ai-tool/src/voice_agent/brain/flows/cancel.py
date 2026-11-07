"""Cancellation flow: look up by phone -> handle 0/1/many appointments -> confirm -> cancel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from voice_agent.brain import responses
from voice_agent.brain.nlu import entities, intents
from voice_agent.brain.state import SessionContext, State
from voice_agent.ports import TurnResult

if TYPE_CHECKING:
    from voice_agent.ports import BookingGateway, Clock


def handle_cancel_turn(
    caller_text: str,
    ctx: SessionContext,
    gateway: BookingGateway,
    clock: Clock,
) -> TurnResult:
    """Process a turn within the appointment cancellation flow."""
    today = clock.today()

    # If caller switches to booking mid-flow
    detected = intents.detect_intent(caller_text)
    if detected == intents.INTENT_BOOK and ctx.state in [
        State.CANCEL_LOOKUP_PHONE,
        State.CANCELLED,
    ]:
        ctx.state = State.COLLECT_SERVICE
        ctx.intent = intents.INTENT_BOOK
        return TurnResult(reply_text=responses.ASK_SERVICE, state=ctx.state.value)

    if ctx.state in [State.START, State.CANCEL_LOOKUP_PHONE]:
        # Try extracting phone number
        phone, is_valid = entities.extract_phone(caller_text)
        if not phone or not is_valid:
            if ctx.patient_phone:
                phone = ctx.patient_phone
            else:
                ctx.increment_fail_count()
                return TurnResult(
                    reply_text=responses.CANCEL_ASK_PHONE, state=State.CANCEL_LOOKUP_PHONE.value
                )

        ctx.patient_phone = phone
        ctx.reset_fail_count()

        # Lookup upcoming appointments
        appts = gateway.find_upcoming_by_phone(phone)
        ctx.user_appointments = appts

        if not appts:
            # Case: no upcoming appointments
            ctx.state = State.END
            return TurnResult(
                reply_text=responses.CANCEL_NO_APPOINTMENTS,
                state=ctx.state.value,
            )

        if len(appts) == 1:
            # Exactly one appointment -> ask for confirmation
            ctx.selected_appointment_id = appts[0][0]
            ctx.selected_slot = appts[0][1]
            ctx.state = State.CANCEL_CONFIRM
            time_str = appts[0][1].start.strftime("%I:%M %p")
            return TurnResult(
                reply_text=responses.format_cancel_confirm(appts[0][1].date.isoformat(), time_str),
                state=ctx.state.value,
            )

        # Multiple appointments -> ask which one
        ctx.state = State.CANCEL_SELECT_APPT
        opts = [f"{s.date.isoformat()} at {s.start.strftime('%I:%M %p')}" for _, s in appts]
        return TurnResult(
            reply_text=responses.format_cancel_choose_which(opts),
            state=ctx.state.value,
        )

    if ctx.state == State.CANCEL_SELECT_APPT:
        # Match which appointment caller selected (by date or order: first/second)
        cleaned = caller_text.lower().strip()
        selected = None
        if "first" in cleaned or "1" in cleaned:
            selected = ctx.user_appointments[0]
        elif "second" in cleaned or "2" in cleaned and len(ctx.user_appointments) > 1:
            selected = ctx.user_appointments[1]
        else:
            # Try date match
            d = entities.extract_date(caller_text, today)
            if d:
                selected = next((item for item in ctx.user_appointments if item[1].date == d), None)

        if selected:
            ctx.selected_appointment_id = selected[0]
            ctx.selected_slot = selected[1]
            ctx.reset_fail_count()
            ctx.state = State.CANCEL_CONFIRM
            time_str = selected[1].start.strftime("%I:%M %p")
            return TurnResult(
                reply_text=responses.format_cancel_confirm(selected[1].date.isoformat(), time_str),
                state=ctx.state.value,
            )

        ctx.increment_fail_count()
        opts = [
            f"{s.date.isoformat()} at {s.start.strftime('%I:%M %p')}"
            for _, s in ctx.user_appointments
        ]
        return TurnResult(
            reply_text=responses.format_cancel_choose_which(opts),
            state=ctx.state.value,
        )

    if ctx.state == State.CANCEL_CONFIRM:
        detected = intents.detect_intent(caller_text)
        if detected == intents.INTENT_CONFIRM:
            ctx.reset_fail_count()
            assert ctx.selected_appointment_id is not None
            assert ctx.selected_slot is not None
            gateway.cancel(ctx.selected_appointment_id)
            ctx.state = State.CANCELLED
            time_str = ctx.selected_slot.start.strftime("%I:%M %p")
            return TurnResult(
                reply_text=responses.format_cancel_success(
                    ctx.selected_slot.date.isoformat(), time_str
                ),
                state=ctx.state.value,
                end_call=True,
                action="appointment_cancelled",
            )
        elif detected == intents.INTENT_REJECT:
            ctx.state = State.END
            return TurnResult(
                reply_text=responses.GOODBYE,
                state=ctx.state.value,
                end_call=True,
            )

        ctx.increment_fail_count()
        assert ctx.selected_slot is not None
        time_str = ctx.selected_slot.start.strftime("%I:%M %p")
        return TurnResult(
            reply_text=responses.format_cancel_confirm(
                ctx.selected_slot.date.isoformat(), time_str
            ),
            state=ctx.state.value,
        )

    return TurnResult(reply_text=responses.FALLBACK, state=ctx.state.value)
