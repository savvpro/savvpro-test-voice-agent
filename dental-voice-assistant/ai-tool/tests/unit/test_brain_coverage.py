"""Targeted tests to cover all edge branches across brain/ modules."""

from __future__ import annotations

from datetime import date, time

from fake_services import FakeBookingGateway, FakeClock

from voice_agent.brain.dialog import handle_turn
from voice_agent.brain.flows.book import _find_nearest_alternatives, handle_book_turn
from voice_agent.brain.flows.cancel import handle_cancel_turn
from voice_agent.brain.flows.reschedule import handle_reschedule_turn
from voice_agent.brain.nlu import entities
from voice_agent.brain.state import SessionContext, State
from voice_agent.ports import SlotInfo


def test_entities_extraction() -> None:
    today = date(2026, 10, 27)

    # Services
    assert entities.extract_service("I have a cavity and tooth ache") == "filling"
    assert entities.extract_service("teeth whitening please") == "whitening"
    assert entities.extract_service("root canal treatment") == "root canal"
    assert entities.extract_service("I want aligners or braces") == "braces consultation"
    assert entities.extract_service("routine examination") == "checkup"
    assert entities.extract_service("scale and polish") == "cleaning"
    assert entities.extract_service("pizza") is None
    assert entities.extract_service("") is None

    # Dates
    assert entities.extract_date("today", today) == today
    assert entities.extract_date("day after tomorrow", today) == date(2026, 10, 29)
    assert entities.extract_date("tomorrow", today) == date(2026, 10, 28)
    assert entities.extract_date("", today) is None
    assert entities.extract_date("not a date", today) is None

    # Times
    t, amb = entities.extract_time("at 5")
    assert amb is True
    t, amb = entities.extract_time("5 o'clock")
    assert amb is True
    t, amb = entities.extract_time("five")
    assert amb is True
    t, amb = entities.extract_time("morning")
    assert t is None and amb is False
    t, amb = entities.extract_time("evening")
    assert t == time(17, 0)
    t, amb = entities.extract_time("10 in the morning")
    assert t == time(10, 0)
    t, amb = entities.extract_time("2 in the afternoon")
    assert t == time(14, 0)
    t, amb = entities.extract_time("12 pm")
    assert t == time(12, 0)
    t, amb = entities.extract_time("12 am")
    assert t == time(0, 0)
    t, amb = entities.extract_time("3:30")
    assert t == time(15, 30)
    t, amb = entities.extract_time("")
    assert t is None and amb is False

    # Phones
    p, v = entities.extract_phone("call me at 0300-1234567")
    assert p == "03001234567" and v is True
    p, v = entities.extract_phone("1234")
    assert p == "1234" and v is False
    p, v = entities.extract_phone("no phone here")
    assert p is None and v is False

    # Names
    assert entities.extract_name("My name is John Doe") == "John Doe"
    assert entities.extract_name("I am Sara Khan") == "Sara Khan"
    assert entities.extract_name("This is Ali") == "Ali"
    assert entities.extract_name("hello please thank you") is None
    assert entities.extract_name("cleaning") is None

    # Alternative choice
    s1 = SlotInfo(today, time(9, 0), time(9, 30))
    s2 = SlotInfo(today, time(11, 0), time(11, 30))
    assert entities.extract_alternative_choice("the first one", [s1, s2]) == s1
    assert entities.extract_alternative_choice("first", [s1, s2]) == s1
    assert entities.extract_alternative_choice("1", [s1, s2]) == s1
    assert entities.extract_alternative_choice("yes", [s1, s2]) == s1
    assert entities.extract_alternative_choice("second", [s1, s2]) == s2
    assert entities.extract_alternative_choice("2", [s1, s2]) == s2
    assert entities.extract_alternative_choice("11:00", [s1, s2]) == s2
    assert entities.extract_alternative_choice("neither", [s1, s2]) is None
    assert entities.extract_alternative_choice("first", []) is None


def test_book_flow_branches() -> None:
    today = date(2026, 10, 27)
    clock = FakeClock(today)
    gateway = FakeBookingGateway(
        available_slots={today: [SlotInfo(today, time(10, 0), time(10, 30))]}
    )

    # Empty nearest alternatives helper
    assert _find_nearest_alternatives(time(10, 0), []) == []

    # Service extraction failure
    ctx = SessionContext(state=State.COLLECT_SERVICE)
    handle_book_turn("blabla", ctx, gateway, clock)
    assert ctx.state == State.COLLECT_SERVICE

    # Date extraction failure
    ctx = SessionContext(state=State.COLLECT_DATE, service="cleaning")
    handle_book_turn("not a date", ctx, gateway, clock)
    assert ctx.state == State.COLLECT_DATE

    # Time extraction failure
    ctx = SessionContext(state=State.COLLECT_TIME, service="cleaning", date=today)
    handle_book_turn("not a time", ctx, gateway, clock)
    assert ctx.state == State.COLLECT_TIME

    # Clarify time unrecognized input
    ctx = SessionContext(state=State.CLARIFY_TIME, service="cleaning", date=today)
    handle_book_turn("maybe later", ctx, gateway, clock)
    assert ctx.state == State.CLARIFY_TIME

    # Offer alternatives rejection
    ctx = SessionContext(
        state=State.OFFER_ALTERNATIVES,
        service="cleaning",
        date=today,
        offered_slots=[SlotInfo(today, time(10, 0), time(10, 30))],
    )
    handle_book_turn("no none of those", ctx, gateway, clock)
    assert ctx.state == State.COLLECT_TIME

    # Offer alternatives unrecognised input
    ctx = SessionContext(
        state=State.OFFER_ALTERNATIVES,
        service="cleaning",
        date=today,
        offered_slots=[SlotInfo(today, time(10, 0), time(10, 30))],
    )
    handle_book_turn("what about tomorrow?", ctx, gateway, clock)
    assert ctx.state == State.OFFER_ALTERNATIVES

    # Name collection failure
    ctx = SessionContext(state=State.COLLECT_NAME, service="cleaning", date=today, time=time(10, 0))
    handle_book_turn("12345", ctx, gateway, clock)
    assert ctx.state == State.COLLECT_NAME

    # Phone confirmation rejection
    ctx = SessionContext(
        state=State.CONFIRM_PHONE,
        service="cleaning",
        date=today,
        time=time(10, 0),
        patient_name="Sara Khan",
        patient_phone="03001234567",
    )
    handle_book_turn("no that is wrong", ctx, gateway, clock)
    assert ctx.state == State.COLLECT_PHONE
    assert ctx.patient_phone is None

    # Phone confirmation unrecognised
    ctx = SessionContext(
        state=State.CONFIRM_PHONE,
        service="cleaning",
        date=today,
        time=time(10, 0),
        patient_name="Sara Khan",
        patient_phone="03001234567",
    )
    handle_book_turn("maybe", ctx, gateway, clock)
    assert ctx.state == State.CONFIRM_PHONE

    # Booking confirmation rejection -> back to COLLECT_TIME
    ctx = SessionContext(
        state=State.CONFIRM_BOOKING,
        service="cleaning",
        date=today,
        time=time(10, 0),
        patient_name="Sara Khan",
        patient_phone="03001234567",
    )
    handle_book_turn("no, change time", ctx, gateway, clock)
    assert ctx.state == State.COLLECT_TIME

    # Booking confirmation unrecognized
    ctx = SessionContext(
        state=State.CONFIRM_BOOKING,
        service="cleaning",
        date=today,
        time=time(10, 0),
        patient_name="Sara Khan",
        patient_phone="03001234567",
    )
    handle_book_turn("what?", ctx, gateway, clock)
    assert ctx.state == State.CONFIRM_BOOKING

    # Intent switch to cancel without phone
    ctx = SessionContext(state=State.COLLECT_TIME)
    handle_book_turn("cancel my appointment", ctx, gateway, clock)
    assert ctx.state == State.CANCEL_LOOKUP_PHONE

    # Intent switch to reschedule without phone
    ctx = SessionContext(state=State.COLLECT_TIME)
    handle_book_turn("reschedule my appointment", ctx, gateway, clock)
    assert ctx.state == State.RESCHEDULE_LOOKUP_PHONE


def test_cancel_flow_branches() -> None:
    today = date(2026, 10, 27)
    clock = FakeClock(today)
    gateway = FakeBookingGateway()

    # Cancel select by date match
    slot1 = SlotInfo(date(2026, 10, 28), time(10, 0), time(10, 30))
    slot2 = SlotInfo(date(2026, 10, 29), time(14, 0), time(14, 30))
    ctx = SessionContext(
        state=State.CANCEL_SELECT_APPT,
        user_appointments=[("id1", slot1), ("id2", slot2)],
    )
    handle_cancel_turn("tomorrow", ctx, gateway, clock)
    assert ctx.state == State.CANCEL_CONFIRM
    assert ctx.selected_appointment_id == "id1"

    # Cancel select unrecognized input
    ctx = SessionContext(
        state=State.CANCEL_SELECT_APPT,
        user_appointments=[("id1", slot1), ("id2", slot2)],
    )
    handle_cancel_turn("not valid", ctx, gateway, clock)
    assert ctx.state == State.CANCEL_SELECT_APPT

    # Cancel confirm unrecognized input
    ctx = SessionContext(
        state=State.CANCEL_CONFIRM,
        selected_appointment_id="id1",
        selected_slot=slot1,
    )
    handle_cancel_turn("what did you say?", ctx, gateway, clock)
    assert ctx.state == State.CANCEL_CONFIRM

    # Mid-flow switch to book
    ctx = SessionContext(state=State.CANCEL_LOOKUP_PHONE)
    handle_cancel_turn("actually book an appointment", ctx, gateway, clock)
    assert ctx.state == State.COLLECT_SERVICE


def test_reschedule_flow_branches() -> None:
    today = date(2026, 10, 27)
    clock = FakeClock(today)
    slot1 = SlotInfo(date(2026, 10, 28), time(10, 0), time(10, 30))
    slot2 = SlotInfo(date(2026, 10, 29), time(14, 0), time(14, 30))

    gateway = FakeBookingGateway(
        available_slots={
            date(2026, 10, 30): [SlotInfo(date(2026, 10, 30), time(15, 0), time(15, 30))]
        },
        existing_appointments={"03001234567": [("id1", slot1), ("id2", slot2)]},
    )

    # Reschedule multiple appointments lookup
    ctx = SessionContext(state=State.START)
    res = handle_reschedule_turn("03001234567", ctx, gateway, clock)
    assert ctx.state.value == State.RESCHEDULE_SELECT_APPT.value

    # Reschedule select by order
    res = handle_reschedule_turn("second", ctx, gateway, clock)
    assert ctx.state.value == State.RESCHEDULE_COLLECT_NEW_SLOT.value
    assert ctx.selected_appointment_id == "id2"

    # Reschedule select invalid input
    ctx = SessionContext(
        state=State.RESCHEDULE_SELECT_APPT,
        user_appointments=[("id1", slot1), ("id2", slot2)],
    )
    res = handle_reschedule_turn("gibberish", ctx, gateway, clock)
    assert ctx.state == State.RESCHEDULE_SELECT_APPT

    # Reschedule collect slot on Sunday
    ctx = SessionContext(
        state=State.RESCHEDULE_COLLECT_NEW_SLOT,
        selected_appointment_id="id1",
        selected_slot=slot1,
    )
    res = handle_reschedule_turn("Sunday at 10 am", ctx, gateway, clock)
    assert "Sunday" in res.reply_text

    # Reschedule collect slot ambiguous time
    res = handle_reschedule_turn("at 5", ctx, gateway, clock)
    assert "morning or evening" in res.reply_text

    # Reschedule collect slot off-hours
    res = handle_reschedule_turn("at 8 pm", ctx, gateway, clock)
    assert "9 AM to 5 PM" in res.reply_text

    # Reschedule collect slot no slots on day
    res = handle_reschedule_turn("tomorrow at 10 am", ctx, gateway, clock)
    assert "no available appointments" in res.reply_text

    # Reschedule reject confirmation
    ctx = SessionContext(
        state=State.RESCHEDULE_CONFIRM,
        selected_appointment_id="id1",
        selected_slot=slot1,
        new_slot=SlotInfo(date(2026, 10, 30), time(15, 0), time(15, 30)),
    )
    res = handle_reschedule_turn("no", ctx, gateway, clock)
    assert ctx.state == State.RESCHEDULE_COLLECT_NEW_SLOT

    # Reschedule confirm unrecognized input
    ctx = SessionContext(
        state=State.RESCHEDULE_CONFIRM,
        selected_appointment_id="id1",
        selected_slot=slot1,
        new_slot=SlotInfo(date(2026, 10, 30), time(15, 0), time(15, 30)),
    )
    res = handle_reschedule_turn("pardon?", ctx, gateway, clock)
    assert ctx.state == State.RESCHEDULE_CONFIRM


def test_dialog_greetings_and_fallbacks() -> None:
    today = date(2026, 10, 27)
    clock = FakeClock(today)
    gateway = FakeBookingGateway()

    # Greeting
    ctx = SessionContext(state=State.START)
    res = handle_turn("hello good morning", ctx, gateway, clock)
    assert "Hello, thank you for calling" in res.reply_text
    assert ctx.state == State.START
