"""Dialog manager and state machine coordinator for the dental voice assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from voice_agent.brain import responses
from voice_agent.brain.flows.book import handle_book_turn
from voice_agent.brain.flows.cancel import handle_cancel_turn
from voice_agent.brain.flows.reschedule import handle_reschedule_turn
from voice_agent.brain.nlu import intents
from voice_agent.brain.state import SessionContext, State
from voice_agent.ports import TurnResult

if TYPE_CHECKING:
    from voice_agent.ports import BookingGateway, Clock


def handle_turn(
    caller_text: str,
    ctx: SessionContext,
    gateway: BookingGateway,
    clock: Clock,
) -> TurnResult:
    """Execute one turn of the conversation, updating ctx in-place."""
    ctx.turn_count += 1

    # 1. Soft cap: max turns check (e.g. 40 turns)
    if ctx.turn_count >= ctx.max_turns:
        ctx.state = State.END
        return TurnResult(
            reply_text=responses.MAX_TURNS_END,
            state=ctx.state.value,
            end_call=True,
            action="max_turns_reached",
        )

    text = caller_text.strip()

    # 2. Handle empty or silence input
    if not text:
        fail = ctx.increment_fail_count()
        if fail >= 3:
            ctx.state = State.HANDOFF
            return TurnResult(
                reply_text=responses.HANDOFF,
                state=ctx.state.value,
                end_call=True,
                action="handoff_operator",
            )
        return TurnResult(
            reply_text=responses.FALLBACK,
            state=ctx.state.value,
        )

    # 3. Handle goodbye / caller wishing to end call
    detected_intent = intents.detect_intent(text)
    if detected_intent == intents.INTENT_GOODBYE:
        ctx.state = State.END
        return TurnResult(
            reply_text=responses.GOODBYE,
            state=ctx.state.value,
            end_call=True,
            action="call_ended_by_user",
        )

    # 4. Handle off-topic questions
    if detected_intent == intents.INTENT_OFF_TOPIC:
        fail = ctx.increment_fail_count()
        if fail >= 3:
            ctx.state = State.HANDOFF
            return TurnResult(
                reply_text=responses.HANDOFF,
                state=ctx.state.value,
                end_call=True,
                action="handoff_operator",
            )
        return TurnResult(
            reply_text=responses.OFF_TOPIC,
            state=ctx.state.value,
        )

    # 5. Intent selection from initial state or intent switches
    if ctx.state == State.START:
        if detected_intent == intents.INTENT_CANCEL:
            ctx.intent = intents.INTENT_CANCEL
            ctx.state = State.CANCEL_LOOKUP_PHONE
            return TurnResult(reply_text=responses.CANCEL_ASK_PHONE, state=ctx.state.value)

        if detected_intent == intents.INTENT_RESCHEDULE:
            ctx.intent = intents.INTENT_RESCHEDULE
            ctx.state = State.RESCHEDULE_LOOKUP_PHONE
            return TurnResult(reply_text=responses.CANCEL_ASK_PHONE, state=ctx.state.value)

        if detected_intent == intents.INTENT_BOOK:
            ctx.intent = intents.INTENT_BOOK
            # Fall through to book turn handler
        else:
            # General greeting if caller just said "hello"
            cleaned = text.lower()
            if any(g in cleaned for g in ["hello", "hi", "hey", "good morning", "good afternoon"]):
                ctx.reset_fail_count()
                return TurnResult(reply_text=responses.GREETING, state=ctx.state.value)
            # Default to booking intent
            ctx.intent = intents.INTENT_BOOK

    # Check consecutive fail_count before dispatching
    if ctx.fail_count >= 3:
        ctx.state = State.HANDOFF
        return TurnResult(
            reply_text=responses.HANDOFF,
            state=ctx.state.value,
            end_call=True,
            action="handoff_operator",
        )

    # 6. Route to appropriate flow
    if (
        ctx.state
        in [
            State.CANCEL_LOOKUP_PHONE,
            State.CANCEL_SELECT_APPT,
            State.CANCEL_CONFIRM,
            State.CANCELLED,
        ]
        or ctx.intent == intents.INTENT_CANCEL
    ):
        res = handle_cancel_turn(text, ctx, gateway, clock)
    elif (
        ctx.state
        in [
            State.RESCHEDULE_LOOKUP_PHONE,
            State.RESCHEDULE_SELECT_APPT,
            State.RESCHEDULE_COLLECT_NEW_SLOT,
            State.RESCHEDULE_OFFER_ALTERNATIVES,
            State.RESCHEDULE_CONFIRM,
            State.RESCHEDULED,
        ]
        or ctx.intent == intents.INTENT_RESCHEDULE
    ):
        res = handle_reschedule_turn(text, ctx, gateway, clock)
    else:
        res = handle_book_turn(text, ctx, gateway, clock)

    # 7. Check if consecutive failures reached threshold after the turn
    if ctx.fail_count >= 3:
        ctx.state = State.HANDOFF
        return TurnResult(
            reply_text=responses.HANDOFF,
            state=ctx.state.value,
            end_call=True,
            action="handoff_operator",
        )

    return res
