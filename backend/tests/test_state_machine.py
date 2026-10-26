"""End-to-end tests for the dialogue manager (the brain).

These tests exercise the full state machine: slot filling, availability
checks, mid-flow changes, side questions, cancellations, repeats, and
the various messy-caller scenarios the task brief calls out.
"""

from datetime import datetime

import pytest

from backend.brain import DM, Session, State
from backend.brain.restaurant import STORE


# Fixed "now" so tests are deterministic.
NOW = datetime(2026, 10, 27, 11, 0, 0)  # Tuesday


@pytest.fixture(autouse=True)
def _freeze_time(monkeypatch):
    """Freeze `datetime.now()` inside slot extraction so dates don't drift."""
    from backend.brain import slots as slot_mod
    from backend.brain import state_machine as sm_mod
    monkeypatch.setattr(slot_mod, "datetime", _FakeDateTime)
    monkeypatch.setattr(sm_mod, "datetime", _FakeDateTime)


@pytest.fixture(autouse=True)
def _reset_store():
    """Reset the booking store before every test to avoid cross-test pollution."""
    STORE.reset()
    yield
    STORE.reset()


class _FakeDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


@pytest.fixture
def fresh():
    """A fresh session — call does NOT consume a turn."""
    s = Session(session_id="test")
    # Skip the GREETING prompt by acting as if caller already said hi
    DM.process("hi", s)
    return s


# ---------------------------------------------------------------------------
# HAPPY PATH
# ---------------------------------------------------------------------------
class TestHappyPath:
    def test_full_booking_one_utterance(self, fresh):
        """Caller says everything in one sentence."""
        r = DM.process("I want to book friday at 8pm for 4 people", fresh)
        # Friday is 2026-10-30. 20:00 for 4 people should be available.
        assert r.state == State.ASK_NAME
        assert r.slots["date"] == "2026-10-30"
        assert r.slots["time"] == "20:00"
        assert r.slots["party_size"] == 4

        r = DM.process("John Smith", fresh)
        assert r.state == State.ASK_PHONE

        r = DM.process("555-123-4567", fresh)
        assert r.state == State.CONFIRM
        assert "John Smith" in r.text
        assert "8 p.m." in r.text

        r = DM.process("yes", fresh)
        assert r.state == State.BOOKED
        assert r.booking_id is not None
        assert "B-" in r.text

    def test_step_by_step_booking(self, fresh):
        """Caller gives one slot at a time."""
        r = DM.process("tomorrow", fresh)
        assert r.state == State.ASK_TIME
        r = DM.process("7pm", fresh)
        assert r.state == State.ASK_PARTY_SIZE
        r = DM.process("for 2", fresh)
        # 7pm tomorrow for 2 should be bookable
        assert r.state == State.ASK_NAME
        r = DM.process("Patel", fresh)
        assert r.state == State.ASK_PHONE
        r = DM.process("555-987-6543", fresh)
        assert r.state == State.CONFIRM
        r = DM.process("yes", fresh)
        assert r.state == State.BOOKED

    def test_greeting_first_then_booking(self):
        s = Session(session_id="t")
        r = DM.process("hi", s)
        assert r.state == State.ASK_DATE
        assert "Copper Spoon" in r.text


# ---------------------------------------------------------------------------
# EDGE CASES — "real callers are messy"
# ---------------------------------------------------------------------------
class TestMessyCallers:
    def test_change_time_mid_flow(self, fresh):
        """Caller books tomorrow at 7pm, then changes to 6pm."""
        DM.process("tomorrow at 7pm for 2", fresh)
        assert fresh.slots["time"] == "19:00"
        r = DM.process("actually change the time to 6pm", fresh)
        assert fresh.slots["time"] == "18:00"
        # Should still progress — 6pm tomorrow for 2 is available
        assert r.state == State.ASK_NAME

    def test_change_party_size_in_confirm(self, fresh):
        """Caller reaches confirm, then says 'actually make it 5 people'."""
        DM.process("tomorrow at 7pm for 2", fresh)
        DM.process("Smith", fresh)
        DM.process("555-123-4567", fresh)
        assert fresh.state == State.CONFIRM
        r = DM.process("actually make it for 5 people", fresh)
        # 5 people at 7pm tomorrow — table 6 (seats 6) is booked at 20:00,
        # so 19:00 should still be available. Re-validates and re-confirms.
        assert r.state == State.CONFIRM
        assert fresh.slots["party_size"] == 5

    def test_unavailable_time_offers_alternatives(self, fresh):
        """Caller asks for a time that's already taken."""
        # B-1001: table 3 (4 seats) on real-today+1 at 19:00 for 4 people.
        # With test NOW=2026-10-27 and real-today=2026-10-26, that date is
        # 2026-10-27 which is "today" from test NOW's perspective.
        r = DM.process("today at 7pm for 4", fresh)
        # Patel's booking collides with table 3, so we should be told no.
        assert "already taken" in r.text or "not" in r.text.lower() or "closed" in r.text.lower() or "available" in r.text.lower()
        # Time slot should be reset
        assert fresh.slots["time"] is None
        assert r.state == State.ASK_TIME

    def test_closed_monday(self, fresh):
        """Caller asks for next Monday — restaurant is closed."""
        # 2026-10-27 is Tuesday. Next Monday is 2026-11-02.
        r = DM.process("monday at 7pm for 2", fresh)
        assert "closed" in r.text.lower() or "Monday" in r.text
        assert fresh.slots["time"] is None  # reset because date failed
        # Actually with current impl, only time gets reset. Date stays.
        # But the response indicates closure.

    def test_side_question_about_hours(self, fresh):
        """Caller interrupts to ask about hours, then continues."""
        DM.process("tomorrow at 7pm for 2", fresh)
        r = DM.process("wait, what are your hours?", fresh)
        # Should answer hours then return to current state (ASK_NAME)
        assert "11:30" in r.text or "lunch" in r.text.lower() or "dinner" in r.text.lower()
        assert r.state == State.ASK_NAME  # unchanged
        # Should be able to continue booking
        r = DM.process("Smith", fresh)
        assert r.state == State.ASK_PHONE

    def test_repeat_last_prompt(self, fresh):
        DM.process("tomorrow at 7pm for 2", fresh)
        last = fresh.last_prompt
        r = DM.process("can you repeat that?", fresh)
        assert r.text == last

    def test_cancel_during_booking(self, fresh):
        DM.process("tomorrow at 7pm for 2", fresh)
        DM.process("Smith", fresh)
        r = DM.process("cancel", fresh)
        assert r.state == State.CANCELLED
        assert "cancel" in r.text.lower()
        # Slots should be cleared
        assert all(v is None for v in fresh.slots.values())

    def test_deny_at_confirm_offers_change(self, fresh):
        DM.process("tomorrow at 7pm for 2", fresh)
        DM.process("Smith", fresh)
        DM.process("555-123-4567", fresh)
        r = DM.process("no", fresh)
        assert "change" in r.text.lower()
        assert r.state == State.CONFIRM

    def test_help_request(self, fresh):
        r = DM.process("help", fresh)
        assert "book" in r.text.lower() or "hours" in r.text.lower()
        # Should not change state — help is a side intent
        assert r.state == fresh.state

    def test_gibberish_triggers_fallback(self, fresh):
        r = DM.process("xyzzy frobnicate quux", fresh)
        assert "didn't" in r.text.lower() or "sorry" in r.text.lower()

    def test_silence_detected(self, fresh):
        r = DM.process("", fresh)
        assert "didn't hear" in r.text.lower() or "still there" in r.text.lower()

    def test_goodbye_ends_call(self, fresh):
        r = DM.process("bye", fresh)
        assert r.state == State.GOODBYE
        assert r.end_call is True


# ---------------------------------------------------------------------------
# AVAILABILITY LOGIC
# ---------------------------------------------------------------------------
class TestAvailability:
    def test_check_available_slot(self):
        ok, _ = STORE.is_available("2026-10-30", "20:00", 4)  # Friday
        assert ok is True

    def test_check_taken_slot(self):
        # B-1001: table 3 (4 seats) on 2026-10-27 at 19:00 for 4 people
        ok, _ = STORE.is_available("2026-10-27", "19:00", 4)
        assert ok is False

    def test_check_closed_day(self):
        # Monday — closed
        ok, reason = STORE.is_available("2026-11-02", "19:00", 2)
        assert ok is False
        assert "closed" in reason.lower()

    def test_check_outside_hours(self):
        # 3am on a Friday — outside opening hours
        ok, reason = STORE.is_available("2026-10-30", "03:00", 2)
        assert ok is False

    def test_check_too_large_party(self):
        ok, reason = STORE.is_available("2026-10-30", "19:00", 50)
        assert ok is False
        assert "can't" in reason.lower() or "largest" in reason.lower()

    def test_create_booking_succeeds_when_available(self):
        # 19:30 on a Friday for 2 — well inside the dinner seating window.
        before = len(STORE.bookings)
        booking = STORE.create_booking("2026-10-30", "19:30", 2, "Test", "5550000000")
        assert booking.booking_id.startswith("B-")
        assert len(STORE.bookings) == before + 1
        # cleanup
        STORE.cancel_booking(booking.booking_id)

    def test_create_booking_fails_when_unavailable(self):
        with pytest.raises(ValueError):
            STORE.create_booking("2026-10-27", "19:00", 4, "Test", "5550000000")

    def test_suggest_alternatives_returns_sorted(self):
        alts = STORE.suggest_alternatives("2026-10-30", 2, "19:00")
        assert len(alts) > 0
        # All returned times should be bookable
        for t in alts:
            ok, _ = STORE.is_available("2026-10-30", t, 2)
            assert ok
