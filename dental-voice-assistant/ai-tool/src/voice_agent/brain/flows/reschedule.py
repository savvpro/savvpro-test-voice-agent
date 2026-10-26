"""Reschedule flow: phone lookup -> select appt -> collect new date/time -> atomic reschedule."""

from __future__ import annotations

from typing import TYPE_CHECKING

from voice_agent.brain import responses
from voice_agent.brain.flows.book import _find_nearest_alternatives
from voice_agent.brain.nlu import entities, intents
from voice_agent.brain.state import SessionContext, State
from voice_agent.ports import TurnResult

if TYPE_CHECKING:
    from voice_agent.ports import BookingGateway, Clock


def handle_reschedule_turn(
    caller_text: str,
    ctx: SessionContext,
    gateway: BookingGateway,
    clock: Clock,
) -> TurnResult:
    """Process a turn within the appointment rescheduling flow."""
    today = clock.today()

    if ctx.state in [State.START, State.RESCHEDULE_LOOKUP_PHONE]:
        phone, is_valid = entities.extract_phone(caller_text)
        if not phone or not is_valid:
            if ctx.patient_phone:
                phone = ctx.patient_phone
            else:
                ctx.increment_fail_count()
                return TurnResult(
                    reply_text=responses.CANCEL_ASK_PHONE, state=State.RESCHEDULE_LOOKUP_PHONE.value
                )

        ctx.patient_phone = phone
        ctx.reset_fail_count()

        appts = gateway.find_upcoming_by_phone(phone)
        ctx.user_appointments = appts

        if not appts:
            ctx.state = State.END
            return TurnResult(
                reply_text=responses.CANCEL_NO_APPOINTMENTS,
                state=ctx.state.value,
            )

        if len(appts) == 1:
            ctx.selected_appointment_id = appts[0][0]
            ctx.selected_slot = appts[0][1]
            ctx.state = State.RESCHEDULE_COLLECT_NEW_SLOT
            return TurnResult(
                reply_text=responses.RESCHEDULE_ASK_NEW_TIME,
                state=ctx.state.value,
            )

        ctx.state = State.RESCHEDULE_SELECT_APPT
        opts = [f"{s.date.isoformat()} at {s.start.strftime('%I:%M %p')}" for _, s in appts]
        return TurnResult(
            reply_text=responses.format_cancel_choose_which(opts),
            state=ctx.state.value,
        )

    if ctx.state == State.RESCHEDULE_SELECT_APPT:
        cleaned = caller_text.lower().strip()
        selected = None
        if "first" in cleaned or "1" in cleaned:
            selected = ctx.user_appointments[0]
        elif "second" in cleaned or "2" in cleaned and len(ctx.user_appointments) > 1:
            selected = ctx.user_appointments[1]
        else:
            d = entities.extract_date(caller_text, today)
            if d:
                selected = next((item for item in ctx.user_appointments if item[1].date == d), None)

        if selected:
            ctx.selected_appointment_id = selected[0]
            ctx.selected_slot = selected[1]
            ctx.reset_fail_count()
            ctx.state = State.RESCHEDULE_COLLECT_NEW_SLOT
            return TurnResult(
                reply_text=responses.RESCHEDULE_ASK_NEW_TIME,
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

    if ctx.state == State.RESCHEDULE_COLLECT_NEW_SLOT:
        d = entities.extract_date(caller_text, today)
        t, is_ambiguous = entities.extract_time(caller_text)

        if is_ambiguous:
            ctx.reset_fail_count()
            return TurnResult(
                reply_text=responses.CLARIFY_TIME_MORNING_EVENING,
                state=ctx.state.value,
            )

        target_date = d or ctx.date or (ctx.selected_slot.date if ctx.selected_slot else today)
        if target_date.weekday() == 6:
            return TurnResult(
                reply_text=responses.CLARIFY_CLOSED_SUNDAY,
                state=ctx.state.value,
            )

        if t:
            # Check off-hours
            if t.hour < 9 or t.hour > 17 or (t.hour == 17 and t.minute > 0):
                return TurnResult(
                    reply_text=responses.CLARIFY_TIME_OFF_HOURS,
                    state=ctx.state.value,
                )

            free = gateway.free_slots(target_date)
            matched = next((s for s in free if s.start == t), None)
            if matched:
                ctx.reset_fail_count()
                ctx.new_slot = matched
                ctx.state = State.RESCHEDULE_CONFIRM
                assert ctx.selected_slot is not None
                return TurnResult(
                    reply_text=responses.format_reschedule_confirm(
                        ctx.selected_slot.date.isoformat(),
                        ctx.selected_slot.start.strftime("%I:%M %p"),
                        matched.date.isoformat(),
                        matched.start.strftime("%I:%M %p"),
                    ),
                    state=ctx.state.value,
                )

            # Slot taken -> offer alternatives
            ctx.state = State.RESCHEDULE_OFFER_ALTERNATIVES
            alts = _find_nearest_alternatives(t, free, limit=2)
            ctx.offered_slots = alts
            if not alts:
                return TurnResult(
                    reply_text=responses.format_offer_no_slots(target_date.isoformat()),
                    state=ctx.state.value,
                )
            slot1_str = alts[0].start.strftime("%I:%M %p")
            slot2_str = alts[1].start.strftime("%I:%M %p") if len(alts) > 1 else ""
            return TurnResult(
                reply_text=responses.format_reschedule_unavailable(slot1_str, slot2_str),
                state=ctx.state.value,
            )

        ctx.increment_fail_count()
        return TurnResult(reply_text=responses.RESCHEDULE_ASK_NEW_TIME, state=ctx.state.value)

    if ctx.state == State.RESCHEDULE_OFFER_ALTERNATIVES:
        picked = entities.extract_alternative_choice(caller_text, ctx.offered_slots)
        if picked:
            ctx.reset_fail_count()
            ctx.new_slot = picked
            ctx.state = State.RESCHEDULE_CONFIRM
            assert ctx.selected_slot is not None
            return TurnResult(
                reply_text=responses.format_reschedule_confirm(
                    ctx.selected_slot.date.isoformat(),
                    ctx.selected_slot.start.strftime("%I:%M %p"),
                    picked.date.isoformat(),
                    picked.start.strftime("%I:%M %p"),
                ),
                state=ctx.state.value,
            )
        ctx.increment_fail_count()
        slot1_str = ctx.offered_slots[0].start.strftime("%I:%M %p") if ctx.offered_slots else ""
        slot2_str = (
            ctx.offered_slots[1].start.strftime("%I:%M %p") if len(ctx.offered_slots) > 1 else ""
        )
        return TurnResult(
            reply_text=responses.format_reschedule_unavailable(slot1_str, slot2_str),
            state=ctx.state.value,
        )

    if ctx.state == State.RESCHEDULE_CONFIRM:
        detected = intents.detect_intent(caller_text)
        if detected == intents.INTENT_CONFIRM:
            ctx.reset_fail_count()
            assert ctx.selected_appointment_id is not None
            assert ctx.new_slot is not None
            res = gateway.reschedule(ctx.selected_appointment_id, ctx.new_slot)
            if res is None:
                # Race condition at reschedule
                free = gateway.free_slots(ctx.new_slot.date)
                alts = _find_nearest_alternatives(ctx.new_slot.start, free, limit=2)
                ctx.offered_slots = alts
                ctx.state = State.RESCHEDULE_OFFER_ALTERNATIVES
                slot1_str = alts[0].start.strftime("%I:%M %p") if alts else ""
                slot2_str = alts[1].start.strftime("%I:%M %p") if len(alts) > 1 else ""
                return TurnResult(
                    reply_text=responses.format_booking_race_lost(slot1_str, slot2_str),
                    state=ctx.state.value,
                )

            ctx.state = State.RESCHEDULED
            return TurnResult(
                reply_text=responses.format_reschedule_success(
                    ctx.new_slot.date.isoformat(),
                    ctx.new_slot.start.strftime("%I:%M %p"),
                ),
                state=ctx.state.value,
                end_call=True,
                action="appointment_rescheduled",
            )
        elif detected == intents.INTENT_REJECT:
            ctx.state = State.RESCHEDULE_COLLECT_NEW_SLOT
            return TurnResult(
                reply_text=responses.RESCHEDULE_ASK_NEW_TIME,
                state=ctx.state.value,
            )

        ctx.increment_fail_count()
        assert ctx.selected_slot is not None
        assert ctx.new_slot is not None
        return TurnResult(
            reply_text=responses.format_reschedule_confirm(
                ctx.selected_slot.date.isoformat(),
                ctx.selected_slot.start.strftime("%I:%M %p"),
                ctx.new_slot.date.isoformat(),
                ctx.new_slot.start.strftime("%I:%M %p"),
            ),
            state=ctx.state.value,
        )

    return TurnResult(reply_text=responses.FALLBACK, state=ctx.state.value)
