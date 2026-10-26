"""Booking flow: handles slot collection, ambiguity, alternatives, phone validation, and booking."""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from voice_agent.brain import responses
from voice_agent.brain.nlu import entities, intents
from voice_agent.brain.state import SessionContext, State
from voice_agent.ports import SlotInfo, TurnResult

if TYPE_CHECKING:
    from voice_agent.ports import BookingGateway, Clock


def _find_nearest_alternatives(
    target_time: time,
    available_slots: list[SlotInfo],
    limit: int = 2,
) -> list[SlotInfo]:
    """Return the up to *limit* nearest available slots to target_time."""
    if not available_slots:
        return []

    target_minutes = target_time.hour * 60 + target_time.minute
    # Sort by absolute distance in minutes
    sorted_slots = sorted(
        available_slots,
        key=lambda s: abs((s.start.hour * 60 + s.start.minute) - target_minutes),
    )
    return sorted_slots[:limit]


def handle_book_turn(
    caller_text: str,
    ctx: SessionContext,
    gateway: BookingGateway,
    clock: Clock,
) -> TurnResult:
    """Process a turn within the appointment booking flow."""
    today = clock.today()

    # 1. Check for mid-flow intent switch to Cancel or Reschedule
    detected = intents.detect_intent(caller_text)
    if detected == intents.INTENT_CANCEL:
        ctx.state = State.CANCEL_LOOKUP_PHONE
        ctx.intent = intents.INTENT_CANCEL
        # Keep name and phone if already collected!
        if ctx.patient_phone:
            # We already have phone, look up directly
            appts = gateway.find_upcoming_by_phone(ctx.patient_phone)
            ctx.user_appointments = appts
            if not appts:
                return TurnResult(
                    reply_text=responses.CANCEL_NO_APPOINTMENTS,
                    state=ctx.state.value,
                )
            if len(appts) == 1:
                ctx.selected_appointment_id = appts[0][0]
                ctx.selected_slot = appts[0][1]
                ctx.state = State.CANCEL_CONFIRM
                return TurnResult(
                    reply_text=responses.format_cancel_confirm(
                        appts[0][1].date.isoformat(),
                        appts[0][1].start.strftime("%I:%M %p"),
                    ),
                    state=ctx.state.value,
                )
            # Multiple appointments
            opts = [f"{s.date.isoformat()} at {s.start.strftime('%I:%M %p')}" for _, s in appts]
            ctx.state = State.CANCEL_SELECT_APPT
            return TurnResult(
                reply_text=responses.format_cancel_choose_which(opts),
                state=ctx.state.value,
            )
        return TurnResult(
            reply_text=responses.CANCEL_ASK_PHONE,
            state=ctx.state.value,
        )

    if detected == intents.INTENT_RESCHEDULE:
        ctx.state = State.RESCHEDULE_LOOKUP_PHONE
        ctx.intent = intents.INTENT_RESCHEDULE
        if ctx.patient_phone:
            appts = gateway.find_upcoming_by_phone(ctx.patient_phone)
            ctx.user_appointments = appts
            if not appts:
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
            opts = [f"{s.date.isoformat()} at {s.start.strftime('%I:%M %p')}" for _, s in appts]
            ctx.state = State.RESCHEDULE_SELECT_APPT
            return TurnResult(
                reply_text=responses.format_cancel_choose_which(opts),
                state=ctx.state.value,
            )
        return TurnResult(
            reply_text=responses.CANCEL_ASK_PHONE,
            state=ctx.state.value,
        )

    # 2. State-specific dispatch in booking flow
    if ctx.state == State.START:
        ctx.state = State.COLLECT_SERVICE
        # Try extracting service/date/time immediately from initial utterance
        srv = entities.extract_service(caller_text)
        if srv:
            ctx.service = srv
            ctx.reset_fail_count()
            d = entities.extract_date(caller_text, today)
            if d:
                ctx.date = d
                ctx.state = State.COLLECT_TIME
                return TurnResult(reply_text=responses.ASK_TIME, state=ctx.state.value)
            ctx.state = State.COLLECT_DATE
            return TurnResult(reply_text=responses.ASK_DATE, state=ctx.state.value)
        return TurnResult(reply_text=responses.ASK_SERVICE, state=ctx.state.value)

    if ctx.state == State.COLLECT_SERVICE:
        srv = entities.extract_service(caller_text)
        if srv:
            ctx.service = srv
            ctx.reset_fail_count()
            ctx.state = State.COLLECT_DATE
            return TurnResult(reply_text=responses.ASK_DATE, state=ctx.state.value)
        ctx.increment_fail_count()
        return TurnResult(reply_text=responses.ASK_SERVICE, state=ctx.state.value)

    if ctx.state == State.COLLECT_DATE:
        d = entities.extract_date(caller_text, today)
        if d:
            ctx.reset_fail_count()
            if d.weekday() == 6:  # Sunday closed
                return TurnResult(
                    reply_text=responses.CLARIFY_CLOSED_SUNDAY,
                    state=ctx.state.value,
                )
            ctx.date = d
            ctx.state = State.COLLECT_TIME
            return TurnResult(reply_text=responses.ASK_TIME, state=ctx.state.value)
        ctx.increment_fail_count()
        return TurnResult(reply_text=responses.ASK_DATE, state=ctx.state.value)

    if ctx.state == State.COLLECT_TIME:
        # Check ambiguous time like "at 5"
        t, is_ambiguous = entities.extract_time(caller_text)
        if is_ambiguous:
            ctx.reset_fail_count()
            ctx.state = State.CLARIFY_TIME
            return TurnResult(
                reply_text=responses.CLARIFY_TIME_MORNING_EVENING,
                state=ctx.state.value,
            )

        if t:
            ctx.reset_fail_count()
            # Validate within clinic hours: 09:00 - 17:00
            if t.hour < 9 or t.hour > 17 or (t.hour == 17 and t.minute > 0):
                return TurnResult(
                    reply_text=responses.CLARIFY_TIME_OFF_HOURS,
                    state=ctx.state.value,
                )

            # Check availability on ctx.date
            assert ctx.date is not None
            free = gateway.free_slots(ctx.date)
            # Find matching slot
            matched = next((s for s in free if s.start == t), None)
            if matched:
                ctx.time = t
                ctx.state = State.COLLECT_NAME
                return TurnResult(reply_text=responses.ASK_NAME, state=ctx.state.value)

            # Slot is unavailable! Offer alternatives
            ctx.state = State.OFFER_ALTERNATIVES
            alts = _find_nearest_alternatives(t, free, limit=2)
            ctx.offered_slots = alts
            if not alts:
                ctx.state = State.COLLECT_DATE
                return TurnResult(
                    reply_text=responses.format_offer_no_slots(ctx.date.isoformat()),
                    state=State.COLLECT_DATE.value,
                )
            slot1_str = alts[0].start.strftime("%I:%M %p")
            slot2_str = alts[1].start.strftime("%I:%M %p") if len(alts) > 1 else "another day"
            return TurnResult(
                reply_text=responses.format_offer_alternatives(slot1_str, slot2_str),
                state=ctx.state.value,
            )

        ctx.increment_fail_count()
        return TurnResult(reply_text=responses.ASK_TIME, state=ctx.state.value)

    if ctx.state == State.CLARIFY_TIME:
        cleaned = caller_text.lower().strip()
        if "morning" in cleaned:
            # 5am is off hours
            ctx.reset_fail_count()
            ctx.state = State.COLLECT_TIME
            return TurnResult(
                reply_text=responses.CLARIFY_TIME_OFF_HOURS,
                state=ctx.state.value,
            )
        if "evening" in cleaned or "pm" in cleaned or "afternoon" in cleaned:
            # 5pm
            t = time(17, 0)
            ctx.reset_fail_count()
            assert ctx.date is not None
            free = gateway.free_slots(ctx.date)
            matched = next((s for s in free if s.start == t), None)
            if matched:
                ctx.time = t
                ctx.state = State.COLLECT_NAME
                return TurnResult(reply_text=responses.ASK_NAME, state=ctx.state.value)
            # Offer alternatives
            ctx.state = State.OFFER_ALTERNATIVES
            alts = _find_nearest_alternatives(t, free, limit=2)
            ctx.offered_slots = alts
            slot1_str = alts[0].start.strftime("%I:%M %p") if alts else ""
            slot2_str = alts[1].start.strftime("%I:%M %p") if len(alts) > 1 else ""
            return TurnResult(
                reply_text=responses.format_offer_alternatives(slot1_str, slot2_str),
                state=ctx.state.value,
            )

        ctx.increment_fail_count()
        return TurnResult(
            reply_text=responses.CLARIFY_TIME_MORNING_EVENING,
            state=ctx.state.value,
        )

    if ctx.state == State.OFFER_ALTERNATIVES:
        picked = entities.extract_alternative_choice(caller_text, ctx.offered_slots)
        if picked:
            ctx.reset_fail_count()
            ctx.time = picked.start
            ctx.state = State.COLLECT_NAME
            return TurnResult(reply_text=responses.ASK_NAME, state=ctx.state.value)
        # If caller rejects or wants another day
        if intents.detect_intent(caller_text) == intents.INTENT_REJECT:
            ctx.reset_fail_count()
            ctx.state = State.COLLECT_TIME
            return TurnResult(reply_text=responses.ASK_TIME, state=ctx.state.value)
        ctx.increment_fail_count()
        slot1_str = ctx.offered_slots[0].start.strftime("%I:%M %p") if ctx.offered_slots else ""
        slot2_str = (
            ctx.offered_slots[1].start.strftime("%I:%M %p") if len(ctx.offered_slots) > 1 else ""
        )
        return TurnResult(
            reply_text=responses.format_offer_alternatives(slot1_str, slot2_str),
            state=ctx.state.value,
        )

    if ctx.state == State.COLLECT_NAME:
        name = entities.extract_name(caller_text)
        if name:
            ctx.patient_name = name
            ctx.reset_fail_count()
            ctx.state = State.COLLECT_PHONE
            return TurnResult(reply_text=responses.ASK_PHONE, state=ctx.state.value)
        ctx.increment_fail_count()
        return TurnResult(reply_text=responses.ASK_NAME, state=ctx.state.value)

    if ctx.state == State.COLLECT_PHONE:
        phone, is_valid = entities.extract_phone(caller_text)
        if not is_valid or not phone:
            ctx.increment_fail_count()
            return TurnResult(reply_text=responses.INVALID_PHONE, state=ctx.state.value)

        ctx.patient_phone = phone
        ctx.reset_fail_count()
        ctx.state = State.CONFIRM_PHONE
        return TurnResult(
            reply_text=responses.format_confirm_phone(phone),
            state=ctx.state.value,
        )

    if ctx.state == State.CONFIRM_PHONE:
        detected = intents.detect_intent(caller_text)
        if detected == intents.INTENT_CONFIRM:
            ctx.phone_confirmed = True
            ctx.reset_fail_count()

            # Duplicate booking check: does this phone already have a booking for this slot?
            assert ctx.patient_phone is not None
            assert ctx.date is not None
            assert ctx.time is not None
            existing = gateway.find_upcoming_by_phone(ctx.patient_phone)
            dup = any(s.date == ctx.date and s.start == ctx.time for _, s in existing)
            if dup:
                ctx.state = State.END
                return TurnResult(
                    reply_text=responses.format_duplicate_booking(
                        ctx.date.isoformat(),
                        ctx.time.strftime("%I:%M %p"),
                    ),
                    state=ctx.state.value,
                )

            ctx.state = State.CONFIRM_BOOKING
            time_str = ctx.time.strftime("%I:%M %p")
            return TurnResult(
                reply_text=responses.format_confirm_booking(
                    ctx.patient_name or "you",
                    ctx.service or "appointment",
                    ctx.date.isoformat(),
                    time_str,
                ),
                state=ctx.state.value,
            )
        elif detected == intents.INTENT_REJECT:
            # Re-collect phone
            ctx.state = State.COLLECT_PHONE
            ctx.patient_phone = None
            return TurnResult(reply_text=responses.ASK_PHONE, state=ctx.state.value)

        ctx.increment_fail_count()
        assert ctx.patient_phone is not None
        return TurnResult(
            reply_text=responses.format_confirm_phone(ctx.patient_phone),
            state=ctx.state.value,
        )

    if ctx.state == State.CONFIRM_BOOKING:
        detected = intents.detect_intent(caller_text)
        if detected == intents.INTENT_CONFIRM:
            ctx.reset_fail_count()
            # Attempt booking via gateway
            assert ctx.date is not None
            assert ctx.time is not None
            end_minutes = ctx.time.hour * 60 + ctx.time.minute + 30
            end_t = time(end_minutes // 60, end_minutes % 60)
            slot = SlotInfo(ctx.date, ctx.time, end_t)

            booking_id = gateway.book(
                patient_name=ctx.patient_name or "Anonymous",
                patient_phone=ctx.patient_phone or "0000000000",
                service=ctx.service or "checkup",
                slot=slot,
            )

            # Race condition check! If gateway.book returned None, slot was taken at confirmation
            if booking_id is None:
                free = gateway.free_slots(ctx.date)
                alts = _find_nearest_alternatives(ctx.time, free, limit=2)
                ctx.offered_slots = alts
                ctx.state = State.OFFER_ALTERNATIVES
                slot1_str = alts[0].start.strftime("%I:%M %p") if alts else "another day"
                slot2_str = alts[1].start.strftime("%I:%M %p") if len(alts) > 1 else "next week"
                return TurnResult(
                    reply_text=responses.format_booking_race_lost(slot1_str, slot2_str),
                    state=ctx.state.value,
                )

            ctx.state = State.BOOKED
            time_str = ctx.time.strftime("%I:%M %p")
            return TurnResult(
                reply_text=responses.format_booking_success(ctx.date.isoformat(), time_str),
                state=ctx.state.value,
                end_call=True,
                action="booking_confirmed",
            )
        elif detected == intents.INTENT_REJECT:
            # Caller wants to change something -> re-offer time selection
            ctx.state = State.COLLECT_TIME
            return TurnResult(reply_text=responses.ASK_TIME, state=ctx.state.value)

        ctx.increment_fail_count()
        time_str = ctx.time.strftime("%I:%M %p") if ctx.time else ""
        return TurnResult(
            reply_text=responses.format_confirm_booking(
                ctx.patient_name or "you",
                ctx.service or "appointment",
                ctx.date.isoformat() if ctx.date else "",
                time_str,
            ),
            state=ctx.state.value,
        )

    return TurnResult(reply_text=responses.FALLBACK, state=ctx.state.value)
