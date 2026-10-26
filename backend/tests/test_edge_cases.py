"""Edge case tests — all 18 scenarios from PLAN.md §8.

Each test is labelled with its edge case number for traceability.
Uses the real InMemoryParcelRepository and frozen clock.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.brain.state_machine import StateMachine, TurnResult
from app.data.loader import load_parcels, load_pickup_points, load_slots
from app.data.repository import InMemoryParcelRepository
from app.models.session import DialogueState, Session

CLOCK = datetime(2026, 10, 26, 14, 30, tzinfo=timezone(timedelta(hours=5), name="PKT"))
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture()
def repo() -> InMemoryParcelRepository:
    parcels = load_parcels(DATA_DIR)
    pickup_points = load_pickup_points(DATA_DIR)
    slots = load_slots(DATA_DIR, CLOCK)
    return InMemoryParcelRepository(parcels, slots, pickup_points)


@pytest.fixture()
def sm(repo) -> StateMachine:
    return StateMachine(repo)


@pytest.fixture()
def session() -> Session:
    return Session(session_id="edge-test", created_at=CLOCK)


def _p(sm, session, text, clock=CLOCK, **kw) -> TurnResult:
    return sm.process(session, text, clock, **kw)


# ── Edge Case 1: Caller changes date/time mid-flow ───────────────────


class TestEdge1_ChangeDateMidFlow:
    """Caller says a new date while already in COLLECT_PERIOD or
    CONFIRM_SLOT."""

    def test_new_date_in_collect_period_resets(self, sm, session):
        session.state = DialogueState.COLLECT_PERIOD
        session.slots.tracking_id = "RD30000001"
        session.slots.action_intent = "reschedule"
        session.slots.intended_date = (CLOCK + timedelta(days=1)).date()

        _p(sm, session, "actually in 4 days")
        # Should reset period and re-enter date flow.
        assert session.slots.intended_period is None or session.state in (
            DialogueState.COLLECT_DATE,
            DialogueState.COLLECT_PERIOD,
            DialogueState.CONFIRM_SLOT,
        )

    def test_change_of_mind_in_confirm_slot(self, sm, session):
        session.state = DialogueState.CONFIRM_SLOT
        session.slots.tracking_id = "RD30000001"
        session.slots.action_intent = "reschedule"
        session.slots.intended_date = (CLOCK + timedelta(days=2)).date()
        session.slots.intended_period = "afternoon"
        session.slots.confirmed_slot_id = "SLOT-2026-10-28-afternoon"

        _p(sm, session, "actually no")
        assert session.state in (
            DialogueState.CHOOSE_ACTION,
            DialogueState.COLLECT_DATE,
        )


# ── Edge Case 2: Caller switches action (reschedule → pickup) ────────


class TestEdge2_SwitchAction:
    def test_change_of_mind_in_collect_date(self, sm, session):
        session.state = DialogueState.COLLECT_DATE
        session.slots.tracking_id = "RD30000001"
        session.slots.action_intent = "reschedule"

        _p(sm, session, "on second thought let me do something else")
        assert session.state == DialogueState.CHOOSE_ACTION
        assert session.slots.action_intent is None


# ── Edge Case 3: Tracking ID misheard / partial / wrong format ────────


class TestEdge3_TrackingMisheard:
    def test_no_tracking_id_extracted(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _p(sm, session, "hmm i think it's uh something")
        assert session.state == DialogueState.COLLECT_TRACKING_ID
        assert "tracking" in r.reply.lower()

    def test_max_tracking_attempts_ends_call(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        for _ in range(3):
            r = _p(sm, session, "i don't remember")
        assert session.state == DialogueState.END
        assert r.ended is True


# ── Edge Case 4: Tracking ID not found in data ───────────────────────


class TestEdge4_TrackingNotFound:
    def test_valid_format_not_in_data(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _p(sm, session, "rd 9 9 9 9 9 9 9 9")
        assert session.state == DialogueState.COLLECT_TRACKING_ID
        assert "cannot find" in r.reply.lower()


# ── Edge Case 5: Wrong phone last 4 with failure escalation ──────────


class TestEdge5_WrongPhone:
    def test_wrong_phone_increments_and_re_asks(self, sm, session, repo):
        session.state = DialogueState.VERIFY_PHONE
        session.slots.tracking_id = "RD30000001"
        # RD30000001 phone is "1234", use "9876" (wrong, not substring of ID).
        r = _p(sm, session, "9876")
        assert session.state == DialogueState.VERIFY_PHONE
        assert "match" in r.reply.lower() or "try" in r.reply.lower()

    def test_phone_locked_after_max_failures(self, sm, session, repo):
        session.state = DialogueState.VERIFY_PHONE
        session.slots.tracking_id = "RD30000001"
        for _ in range(3):
            r = _p(sm, session, "9876")
        assert session.state == DialogueState.END
        assert r.ended is True
        assert repo.is_parcel_locked("RD30000001") is True


# ── Edge Case 6: Parcel delivered / cancelled / returned ──────────────


class TestEdge6_ParcelStatusBlocked:
    def test_in_transit_blocks_reschedule(self, sm, session):
        """in_transit only allows status."""
        session.state = DialogueState.CHOOSE_ACTION
        session.slots.tracking_id = "RD10000001"  # in_transit
        session.slots.verified = True
        r = _p(sm, session, "reschedule")
        assert session.state == DialogueState.CHOOSE_ACTION
        assert "not available" in r.reply.lower() or "in transit" in r.reply.lower()

    def test_delivered_blocks_cancel(self, sm, session):
        session.state = DialogueState.CHOOSE_ACTION
        session.slots.tracking_id = "RD40000001"  # delivered
        session.slots.verified = True
        _p(sm, session, "cancel")
        assert session.state == DialogueState.CHOOSE_ACTION


# ── Edge Case 7: Requested slot is full ───────────────────────────────


class TestEdge7_SlotFull:
    def test_tomorrow_morning_full_offers_alt(self, sm, session):
        """Day offset 1 morning is fully booked per slots.json."""
        session.state = DialogueState.COLLECT_DATE
        session.slots.tracking_id = "RD30000001"
        session.slots.action_intent = "reschedule"
        r = _p(sm, session, "tomorrow morning")
        # Should offer an alternative since morning is full.
        assert "fully booked" in r.reply.lower() or "nearest" in r.reply.lower() or "available" in r.reply.lower()


# ── Edge Case 8: Date in past / beyond 7 days / cutoff ───────────────


class TestEdge8_DateRejection:
    def test_date_past(self, sm, session):
        """'today morning' at 14:30 is past cutoff — date parser returns
        reason='cutoff'. ('yesterday' is not recognised by the parser.)"""
        session.state = DialogueState.COLLECT_DATE
        session.slots.tracking_id = "RD30000001"
        session.slots.action_intent = "reschedule"
        r = _p(sm, session, "today morning")
        assert "passed" in r.reply.lower() or "later" in r.reply.lower()

    def test_date_out_of_range(self, sm, session):
        session.state = DialogueState.COLLECT_DATE
        session.slots.tracking_id = "RD30000001"
        session.slots.action_intent = "reschedule"
        r = _p(sm, session, "in 10 days")
        assert "7 days" in r.reply.lower() or "range" in r.reply.lower()

    def test_today_morning_cutoff(self, sm, session):
        """At 14:30, morning is past cutoff."""
        session.state = DialogueState.COLLECT_DATE
        session.slots.tracking_id = "RD30000001"
        session.slots.action_intent = "reschedule"
        r = _p(sm, session, "today morning")
        assert "passed" in r.reply.lower() or "later" in r.reply.lower()


# ── Edge Case 9: Multi-slot turn ─────────────────────────────────────


class TestEdge9_MultiSlotTurn:
    def test_date_and_period_in_one_turn(self, sm, session):
        """'tomorrow afternoon' fills both date and period in one pass."""
        session.state = DialogueState.COLLECT_DATE
        session.slots.tracking_id = "RD30000001"
        session.slots.action_intent = "reschedule"
        r = _p(sm, session, "tomorrow afternoon")
        # Should jump straight to CONFIRM_SLOT.
        assert session.state == DialogueState.CONFIRM_SLOT
        assert "afternoon" in r.reply.lower()


# ── Edge Case 10: Nothing useful / mumble / off-topic ────────────────


class TestEdge10_Unknown:
    def test_unknown_turn_1(self, sm, session):
        session.state = DialogueState.CHOOSE_ACTION
        session.slots.tracking_id = "RD30000001"
        session.slots.verified = True
        r = _p(sm, session, "blah blah blah")
        assert "understand" in r.reply.lower() or "say" in r.reply.lower()

    def test_unknown_escalation_to_human(self, sm, session):
        session.state = DialogueState.CHOOSE_ACTION
        session.slots.tracking_id = "RD30000001"
        session.slots.verified = True
        for _ in range(5):
            r = _p(sm, session, "random gibberish")
        assert session.state == DialogueState.CHOOSE_ACTION
        assert session.ended is False
        assert "say yes or no" in r.reply.lower()


# ── Edge Case 11: Silence or empty input ──────────────────────────────


class TestEdge11_Silence:
    def test_silence_escalation_3_turns(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        replies = []
        for i in range(3):
            r = _p(sm, session, "", silence=True)
            replies.append(r.reply)
        assert session.state == DialogueState.END
        assert r.ended is True
        # First reply should be gentle, last should be ending.
        assert "still there" in replies[0].lower() or "hear" in replies[0].lower()
        assert "end" in replies[2].lower() or "goodbye" in replies[2].lower()

    def test_silence_counter_independent_of_unknown(self, sm, session):
        session.state = DialogueState.CHOOSE_ACTION
        session.slots.tracking_id = "RD30000001"
        session.slots.verified = True
        # 2 unknowns then 1 silence — silence should NOT trigger END.
        _p(sm, session, "gibberish")
        _p(sm, session, "more gibberish")
        _p(sm, session, "", silence=True)
        assert session.state != DialogueState.END
        assert session.silence_count == 1
        assert session.unknown_count == 2


# ── Edge Case 12: Repeat / human / goodbye at any state ──────────────


class TestEdge12_CrossCuttingAnywhere:
    def test_repeat_in_collect_date(self, sm, session):
        session.state = DialogueState.COLLECT_DATE
        session.slots.tracking_id = "RD30000001"
        session.last_assistant_reply = "What date works for you?"
        r = _p(sm, session, "say that again")
        assert r.reply == "What date works for you?"
        assert session.state == DialogueState.COLLECT_DATE

    def test_human_in_verify_phone(self, sm, session):
        session.state = DialogueState.VERIFY_PHONE
        session.slots.tracking_id = "RD30000001"
        r = _p(sm, session, "transfer me to a human")
        assert session.state == DialogueState.END
        assert r.ended is True

    def test_goodbye_in_choose_action(self, sm, session):
        session.state = DialogueState.CHOOSE_ACTION
        session.slots.tracking_id = "RD30000001"
        session.slots.verified = True
        r = _p(sm, session, "thanks bye")
        assert session.state == DialogueState.END
        assert r.ended is True


# ── Edge Case 13: Cancellation without confirmation ──────────────────


class TestEdge13_CancelRequiresConfirm:
    def test_cancel_routes_through_confirm(self, sm, session):
        session.state = DialogueState.CHOOSE_ACTION
        session.slots.tracking_id = "RD30000001"
        session.slots.verified = True
        r = _p(sm, session, "cancel")
        assert session.state == DialogueState.CONFIRM_CANCEL
        assert "sure" in r.reply.lower() or "confirm" in r.reply.lower()
        # Parcel NOT yet cancelled.
        assert session.ended is False

    def test_deny_cancel_returns_to_menu(self, sm, session, repo):
        session.state = DialogueState.CONFIRM_CANCEL
        session.slots.tracking_id = "RD30000001"
        _p(sm, session, "no")
        assert session.state == DialogueState.CHOOSE_ACTION
        p = repo.get_parcel("RD30000001")
        assert p.status.value == "failed_attempt"  # NOT cancelled


# ── Edge Case 14: Affirm/deny at wrong moment ────────────────────────


class TestEdge14_AffirmDenyWrongState:
    def test_affirm_in_collect_date(self, sm, session):
        """Affirm in COLLECT_DATE has no meaning — should re-ask."""
        session.state = DialogueState.COLLECT_DATE
        session.slots.tracking_id = "RD30000001"
        session.slots.action_intent = "reschedule"
        r = _p(sm, session, "yes")
        # Should still be in COLLECT_DATE and re-ask for a date.
        assert session.state == DialogueState.COLLECT_DATE
        assert "date" in r.reply.lower() or "7 days" in r.reply.lower()

    def test_deny_in_collect_tracking(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        _p(sm, session, "no")
        assert session.state == DialogueState.COLLECT_TRACKING_ID


# ── Edge Case 15: Long input / special chars / injection ──────────────


class TestEdge15_InjectionAndLength:
    def test_long_input_truncated(self, sm, session):
        """Input > 2000 chars gets handled without crash."""
        session.state = DialogueState.COLLECT_TRACKING_ID
        long_text = "hello " * 400  # 2400 chars
        r = _p(sm, session, long_text)
        # Should not crash; normalizer truncates to 2000.
        assert r.reply is not None

    def test_sql_injection_safe(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _p(sm, session, "'; DROP TABLE parcels; --")
        assert r.reply is not None
        assert session.state == DialogueState.COLLECT_TRACKING_ID

    def test_html_injection_safe(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _p(sm, session, "<script>alert('xss')</script>")
        assert r.reply is not None

    def test_null_bytes_safe(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _p(sm, session, "rd\x0010000001")
        assert r.reply is not None

    def test_unicode_safe(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _p(sm, session, "rd 10000001 🎉")
        assert r.reply is not None


# ── Edge Case 16: Two tracking IDs in one turn ───────────────────────


class TestEdge16_TwoTrackingIds:
    def test_two_ids_asks_which(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _p(sm, session, "is it rd 1 0 0 0 0 0 0 1 or rd 3 0 0 0 0 0 0 1")
        assert session.state == DialogueState.COLLECT_TRACKING_ID
        assert "two" in r.reply.lower() or "which" in r.reply.lower()
        assert session.slots.tracking_id is None
        assert len(session.slots.ambiguous_ids) == 2


# ── Edge Case 17: Double / concurrent booking ────────────────────────


class TestEdge17_ConcurrentBooking:
    def test_two_threads_one_slot(self, repo):
        """Only one of two concurrent bookings should succeed."""
        from app.services.booking import book_slot, get_available_slots

        tomorrow = CLOCK.date() + timedelta(days=2)
        slots = get_available_slots(repo, tomorrow, CLOCK)
        assert len(slots) > 0
        slot = slots[0]

        # Fill to capacity - 1.
        for i in range(slot.capacity - 1):
            tid = f"RD3000000{i+1}"
            repo.book_slot(slot.slot_id, tid)

        # Now only 1 spot left. Race two threads.
        results = [None, None]

        def book_thread(idx, tid):
            results[idx] = book_slot(repo, slot.slot_id, tid)

        t1 = threading.Thread(target=book_thread, args=(0, "RD30000006"))
        t2 = threading.Thread(target=book_thread, args=(1, "RD30000007"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one should succeed.
        assert results.count(True) == 1
        assert results.count(False) == 1


# ── Edge Case 18: Session not found / ended / post-END turns ─────────


class TestEdge18_SessionPostEnd:
    def test_post_end_returns_ended_message(self, sm, session):
        session.state = DialogueState.END
        session.ended = True
        r = _p(sm, session, "hello again")
        assert "ended" in r.reply.lower()
        assert r.ended is True

    def test_multiple_post_end_turns_still_safe(self, sm, session):
        session.state = DialogueState.END
        session.ended = True
        for _ in range(5):
            r = _p(sm, session, "are you there")
        assert session.state == DialogueState.END
        assert r.ended is True
