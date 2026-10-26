"""Dialogue-engine scenarios: happy path, messy callers, unavailable slots."""

from __future__ import annotations

import pytest

from app.engine import availability
from app.engine.dialogue import DialogueEngine
from app.models import DialogueState


@pytest.fixture
def engine():
    return DialogueEngine()


def _say(engine: DialogueEngine, sid: str, text: str):
    return engine.handle_turn(sid, text)


def test_happy_path_booking(engine):
    sid = "happy"
    r = engine.reset(sid)
    assert r.state == DialogueState.ASK_DATE.value
    assert "Harbor Lights" in r.reply

    r = _say(engine, sid, "tomorrow")
    assert r.slots.date is not None
    assert r.state == DialogueState.ASK_TIME.value

    r = _say(engine, sid, "7 pm")
    assert r.slots.time == "19:00"
    assert r.state == DialogueState.ASK_PARTY.value

    r = _say(engine, sid, "4")
    assert r.slots.party_size == 4
    assert r.state == DialogueState.CONFIRM.value
    assert r.decision.action == "ask_confirm"

    r = _say(engine, sid, "yes")
    assert r.state == DialogueState.BOOKED.value
    assert r.booking is not None
    assert r.booking.party_size == 4
    assert r.booking.id.startswith("HLB-")
    listed = availability.store.list_bookings()
    assert any(b.id == r.booking.id for b in listed)


def test_all_slots_in_one_turn(engine):
    sid = "bundle"
    engine.reset(sid)
    r = _say(engine, sid, "Friday at 8pm for 2 people")
    assert r.slots.date is not None
    assert r.slots.time == "20:00"
    assert r.slots.party_size == 2
    assert r.state == DialogueState.CONFIRM.value

    r = _say(engine, sid, "book it")
    assert r.state == DialogueState.BOOKED.value
    assert r.booking is not None


def test_change_time_mid_flow(engine):
    sid = "change-time"
    engine.reset(sid)
    _say(engine, sid, "tomorrow")
    _say(engine, sid, "6 pm")
    r = _say(engine, sid, "actually make it 8 instead")
    assert r.slots.time == "20:00"
    assert r.slots.date is not None
    assert r.state in (
        DialogueState.ASK_PARTY.value,
        DialogueState.CONFIRM.value,
    )


def test_change_date_at_confirm(engine):
    sid = "change-date"
    engine.reset(sid)
    _say(engine, sid, "tomorrow at 7 for 3")
    r = _say(engine, sid, "wait, change the day to Friday")
    assert r.slots.date is not None
    assert r.decision.intent in ("change_date", "provide_info")
    if r.state != DialogueState.CONFIRM.value:
        if not r.slots.time:
            r = _say(engine, sid, "7 pm")
        if not r.slots.party_size:
            r = _say(engine, sid, "3")
    r = _say(engine, sid, "yes")
    assert r.state == DialogueState.BOOKED.value


def test_unavailable_offers_alternatives(engine):
    sid = "full"
    date = "2026-10-28"
    for seats in (2, 2, 4, 4, 6, 6, 8, 10):
        assert availability.store.book(date, "19:00", seats) is not None

    engine.reset(sid)
    _say(engine, sid, "October 28")
    _say(engine, sid, "7 pm")
    r = _say(engine, sid, "2 people")
    assert r.decision.action == "offer_alternatives"
    assert r.slots.time is None
    assert len(r.alternatives) > 0
    alt = r.alternatives[0]
    r = _say(engine, sid, alt if ":" in alt else f"{alt}")
    h, m = map(int, alt.split(":"))
    label = f"{h % 12 or 12}:{m:02d} {'pm' if h >= 12 else 'am'}"
    if r.slots.time is None:
        r = _say(engine, sid, label)
    assert r.slots.time == alt or r.state in (
        DialogueState.CONFIRM.value,
        DialogueState.ASK_PARTY.value,
        DialogueState.ASK_TIME.value,
    )
    if r.state == DialogueState.ASK_TIME.value:
        r = _say(engine, sid, label)
    if r.state == DialogueState.ASK_PARTY.value:
        r = _say(engine, sid, "2")
    if r.state == DialogueState.CONFIRM.value:
        r = _say(engine, sid, "yes")
    assert r.state == DialogueState.BOOKED.value


def test_cancel_mid_flow(engine):
    sid = "cancel"
    engine.reset(sid)
    _say(engine, sid, "tomorrow")
    r = _say(engine, sid, "never mind, cancel")
    assert r.state == DialogueState.CANCELLED.value
    assert "cancel" in r.reply.lower() or "cancelled" in r.reply.lower()


def test_unclear_asks_again(engine):
    sid = "unclear"
    engine.reset(sid)
    r = _say(engine, sid, "blah blah purple elephant")
    assert r.state == DialogueState.ASK_DATE.value
    assert r.decision.action in ("clarify_date", "ask_date")
    assert "date" in r.reply.lower() or "day" in r.reply.lower()


def test_out_of_scope_redirect(engine):
    sid = "oos"
    engine.reset(sid)
    r = _say(engine, sid, "what's the weather like")
    assert r.decision.intent == "out_of_scope"
    assert "booking" in r.reply.lower() or "table" in r.reply.lower()


def test_reject_time_outside_hours(engine):
    sid = "late"
    engine.reset(sid)
    _say(engine, sid, "tomorrow")
    r = _say(engine, sid, "11 pm")
    assert r.decision.action == "reject_time"
    assert r.slots.time is None


def test_deny_at_confirm_allows_revision(engine):
    sid = "deny"
    engine.reset(sid)
    _say(engine, sid, "tomorrow at 7 for 2")
    r = _say(engine, sid, "no")
    assert r.decision.action == "revise"
    r = _say(engine, sid, "Friday at 8pm for 2")
    if r.state == DialogueState.CONFIRM.value:
        r = _say(engine, sid, "yes")
    assert r.state == DialogueState.BOOKED.value


def test_booking_survives_store_rebind(engine, tmp_path):
    """Bookings stay on disk — reopening the same DB file still sees them."""
    sid = "persist"
    engine.reset(sid)
    _say(engine, sid, "tomorrow at 7 for 2")
    r = _say(engine, sid, "yes")
    assert r.booking is not None
    bid = r.booking.id
    db_file = availability.store._path
    other = availability.AvailabilityStore(db_file)
    found = other.get_booking(bid)
    assert found is not None
    assert found.party_size == 2


def test_admin_cancel_frees_slot(engine):
    sid = "admin-cancel"
    engine.reset(sid)
    _say(engine, sid, "tomorrow at 7pm for 2")
    r = _say(engine, sid, "yes")
    assert r.booking is not None
    bid = r.booking.id
    booked_date = r.booking.date
    assert availability.store.cancel_booking(bid) is True
    got = availability.store.get_booking(bid)
    assert got is not None and got.status == "cancelled"
    assert availability.store.is_available(booked_date, "19:00", 2)
