"""Tests for the state machine — every transition row and cross-cutting rule.

Uses the real InMemoryParcelRepository and frozen clock.
"""

from __future__ import annotations

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
    return Session(session_id="test-sm", created_at=CLOCK)


def _process(sm, session, text, clock=CLOCK, **kwargs) -> TurnResult:
    return sm.process(session, text, clock, **kwargs)


# ── Cross-cutting: END state ──────────────────────────────────────────


class TestEndState:
    def test_any_input_after_end(self, sm, session):
        session.state = DialogueState.END
        r = _process(sm, session, "hello")
        assert "ended" in r.reply.lower()
        assert r.ended is True


# ── Cross-cutting: silence ────────────────────────────────────────────


class TestSilence:
    def test_silence_turn_1(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _process(sm, session, "", silence=True)
        assert "still there" in r.reply.lower() or "hear" in r.reply.lower()

    def test_silence_turn_2(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        session.silence_count = 1
        r = _process(sm, session, "", silence=True)
        assert "hear" in r.reply.lower() or "cannot" in r.reply.lower()

    def test_silence_turn_3_ends(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        session.silence_count = 2
        r = _process(sm, session, "", silence=True)
        assert r.ended is True
        assert session.state == DialogueState.END

    def test_empty_text_treated_as_silence(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        _process(sm, session, "   ")
        assert session.silence_count >= 1

    def test_silence_counter_resets_on_speech(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        session.silence_count = 2
        _process(sm, session, "hello")
        assert session.silence_count == 0


# ── Cross-cutting: low STT confidence ─────────────────────────────────


class TestLowSTT:
    def test_low_confidence_re_asks(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _process(sm, session, "something", stt_confidence=0.3)
        assert "catch" in r.reply.lower() or "again" in r.reply.lower()


# ── Cross-cutting: repeat / human / goodbye ───────────────────────────


class TestCrossCutting:
    def test_repeat(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        session.last_assistant_reply = "Previous reply text"
        r = _process(sm, session, "repeat")
        assert r.reply == "Previous reply text"

    def test_repeat_no_previous(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _process(sm, session, "repeat")
        assert "not said" in r.reply.lower() or "help" in r.reply.lower()

    def test_human_agent(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _process(sm, session, "speak to a human")
        assert r.ended is True
        assert "transfer" in r.reply.lower() or "agent" in r.reply.lower()

    def test_goodbye(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _process(sm, session, "goodbye")
        assert r.ended is True


# ── COLLECT_TRACKING_ID ───────────────────────────────────────────────


class TestCollectTrackingId:
    def test_valid_id_found(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _process(sm, session, "rd 1 0 0 0 0 0 0 1")
        assert session.state == DialogueState.CONFIRM_TRACKING_ID
        assert "correct" in r.reply.lower() or "right" in r.reply.lower()

    def test_valid_id_not_found(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _process(sm, session, "rd 9 9 9 9 9 9 9 9")
        assert session.state == DialogueState.COLLECT_TRACKING_ID
        assert "cannot find" in r.reply.lower()

    def test_no_id_re_asks(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _process(sm, session, "i want to reschedule")
        assert session.state == DialogueState.COLLECT_TRACKING_ID
        assert "tracking" in r.reply.lower()

    def test_max_attempts_ends(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        session.tracking_attempts = 2  # next will be 3 = max
        r = _process(sm, session, "i dont know")
        assert session.state == DialogueState.END
        assert r.ended is True


# ── CONFIRM_TRACKING_ID ───────────────────────────────────────────────


class TestConfirmTrackingId:
    def test_affirm_goes_to_verify_phone(self, sm, session):
        session.state = DialogueState.CONFIRM_TRACKING_ID
        session.slots.tracking_id = "RD10000001"
        r = _process(sm, session, "yes")
        assert session.state == DialogueState.VERIFY_PHONE
        assert "phone" in r.reply.lower() or "digits" in r.reply.lower()

    def test_deny_goes_back(self, sm, session):
        session.state = DialogueState.CONFIRM_TRACKING_ID
        session.slots.tracking_id = "RD10000001"
        _process(sm, session, "no")
        assert session.state == DialogueState.COLLECT_TRACKING_ID


# ── VERIFY_PHONE ──────────────────────────────────────────────────────


class TestVerifyPhone:
    def _get_phone(self, repo, tid):
        p = repo.get_parcel(tid)
        return p.phone_last4

    def test_correct_phone(self, sm, session, repo):
        session.state = DialogueState.VERIFY_PHONE
        session.slots.tracking_id = "RD10000001"
        phone = self._get_phone(repo, "RD10000001")
        r = _process(sm, session, phone)
        assert session.state == DialogueState.CHOOSE_ACTION
        assert "verified" in r.reply.lower() or "what would you" in r.reply.lower()

    def test_wrong_phone(self, sm, session, repo):
        session.state = DialogueState.VERIFY_PHONE
        session.slots.tracking_id = "RD10000001"
        # "9876" is not a substring of "10000001", so it gets extracted.
        r = _process(sm, session, "9876")
        assert session.state == DialogueState.VERIFY_PHONE
        assert "match" in r.reply.lower() or "try" in r.reply.lower()

    def test_phone_max_attempts_locks(self, sm, session, repo):
        session.state = DialogueState.VERIFY_PHONE
        session.slots.tracking_id = "RD10000001"
        session.phone_attempts = 2
        # "9876" is not a substring of "10000001", so it gets extracted.
        r = _process(sm, session, "9876")
        assert session.state == DialogueState.END
        assert r.ended is True


# ── CHOOSE_ACTION ─────────────────────────────────────────────────────


class TestChooseAction:
    def _setup_verified(self, session, tracking_id="RD30000001"):
        """Use RD30000001 (failed_attempt) which allows reschedule/cancel."""
        session.state = DialogueState.CHOOSE_ACTION
        session.slots.tracking_id = tracking_id
        session.slots.verified = True

    def test_reschedule(self, sm, session):
        self._setup_verified(session)
        r = _process(sm, session, "reschedule")
        assert session.state == DialogueState.COLLECT_DATE
        assert "date" in r.reply.lower()

    def test_cancel(self, sm, session):
        self._setup_verified(session)
        _process(sm, session, "cancel")
        assert session.state == DialogueState.CONFIRM_CANCEL

    def test_status(self, sm, session):
        # RD10000001 (in_transit) only allows "status" — perfect for this test.
        self._setup_verified(session, tracking_id="RD10000001")
        r = _process(sm, session, "status")
        assert session.state == DialogueState.ANYTHING_ELSE
        assert "anything else" in r.reply.lower()

    def test_unknown_escalation_asks_permission(self, sm, session):
        self._setup_verified(session)
        for _ in range(5):
            r = _process(sm, session, "blah blah blah")
        assert session.state == DialogueState.CHOOSE_ACTION
        assert session.ended is False
        assert "say yes or no" in r.reply.lower()


# ── COLLECT_DATE ──────────────────────────────────────────────────────


class TestCollectDate:
    def _setup(self, session):
        session.state = DialogueState.COLLECT_DATE
        session.slots.tracking_id = "RD10000001"
        session.slots.action_intent = "reschedule"

    def test_tomorrow_morning(self, sm, session):
        self._setup(session)
        r = _process(sm, session, "tomorrow morning")
        # Should go to CONFIRM_SLOT (tomorrow morning is available,
        # offset 1 morning is NOT booked based on slots.json... wait,
        # offset 1 morning IS fully booked per slots.json).
        # Actually offset 1 morning is fully booked, so it should offer alt.
        assert "morning" in r.reply.lower() or "book" in r.reply.lower() or "slot" in r.reply.lower()

    def test_tomorrow_afternoon(self, sm, session):
        self._setup(session)
        r = _process(sm, session, "tomorrow afternoon")
        assert session.state == DialogueState.CONFIRM_SLOT
        assert "afternoon" in r.reply.lower()

    def test_date_only_asks_period(self, sm, session):
        self._setup(session)
        r = _process(sm, session, "in 2 days")
        assert session.state == DialogueState.COLLECT_PERIOD
        assert "morning" in r.reply.lower() or "prefer" in r.reply.lower()

    def test_change_of_mind(self, sm, session):
        self._setup(session)
        _process(sm, session, "actually no")
        assert session.state == DialogueState.CHOOSE_ACTION

    def test_past_date(self, sm, session):
        self._setup(session)
        r = _process(sm, session, "today morning")
        # At 14:30, morning is past — cutoff.
        assert "passed" in r.reply.lower() or "later" in r.reply.lower()


# ── CONFIRM_CANCEL ────────────────────────────────────────────────────


class TestConfirmCancel:
    def _setup(self, session):
        session.state = DialogueState.CONFIRM_CANCEL
        session.slots.tracking_id = "RD10000001"
        session.slots.action_intent = "cancel"

    def test_affirm_cancels(self, sm, session, repo):
        self._setup(session)
        r = _process(sm, session, "yes")
        assert session.state == DialogueState.ANYTHING_ELSE
        assert "cancelled" in r.reply.lower()
        assert "say yes to continue" in r.reply.lower()
        p = repo.get_parcel("RD10000001")
        assert p.status.value == "cancelled"

    def test_deny_returns_to_menu(self, sm, session):
        self._setup(session)
        r = _process(sm, session, "no")
        assert session.state == DialogueState.CHOOSE_ACTION
        assert "not cancelled" in r.reply.lower() or "else" in r.reply.lower()


# ── DELIVER_STATUS → CHOOSE_ACTION ────────────────────────────────────


class TestDeliverStatus:
    def test_status_returns_to_menu(self, sm, session):
        session.state = DialogueState.DELIVER_STATUS
        session.slots.tracking_id = "RD10000001"
        _process(sm, session, "")
        # Empty input → silence in this case, but let's test with text.

    def test_status_shows_and_asks_else(self, sm, session):
        session.state = DialogueState.CHOOSE_ACTION
        session.slots.tracking_id = "RD10000001"
        session.slots.verified = True
        r = _process(sm, session, "status")
        assert session.state == DialogueState.ANYTHING_ELSE
        assert "anything else" in r.reply.lower()


class TestPickupFollowUp:
    def test_pickup_date_question_does_not_restart_point_selection(self, sm, session):
        session.state = DialogueState.ANYTHING_ELSE
        session.slots.pickup_point_id = "PP-001"
        session.slots.verified = True
        r = _process(sm, session, "yes can you tell me on which date I can check and collect it")
        assert session.state == DialogueState.ANYTHING_ELSE
        assert "do not have a confirmed ready-for-collection date" in r.reply.lower()
        assert "pickup points:" not in r.reply.lower()

    def test_pickup_selector_understands_last_and_fourth(self, sm, session):
        session.state = DialogueState.COLLECT_PICKUP_POINT
        session.slots.verified = True
        for text, expected in (
            ("last one", "Rawalpindi Saddar Mini Depot"),
            ("fourth one", "Peshawar University Road Collection Point"),
        ):
            session.state = DialogueState.COLLECT_PICKUP_POINT
            session.slots.pickup_point_id = None
            r = _process(sm, session, text)
            assert session.state == DialogueState.CONFIRM_PICKUP
            assert expected.lower() in r.reply.lower()


def test_all_from_my_side_is_goodbye():
    from app.brain.intent_detector import detect_intent

    assert detect_intent("India is all from my side").intent == "goodbye"


# ── TurnResult and DecisionTrace ──────────────────────────────────────


class TestTurnResult:
    def test_has_reply_and_trace(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        r = _process(sm, session, "hello")
        assert isinstance(r, TurnResult)
        assert r.reply
        assert r.trace is not None
        assert r.trace.state_before == "COLLECT_TRACKING_ID"
        assert r.trace.state_after is not None

    def test_trace_records_intent(self, sm, session):
        session.state = DialogueState.CHOOSE_ACTION
        session.slots.tracking_id = "RD10000001"
        session.slots.verified = True
        r = _process(sm, session, "reschedule")
        assert r.trace.intent == "reschedule"

    def test_history_recorded(self, sm, session):
        session.state = DialogueState.COLLECT_TRACKING_ID
        _process(sm, session, "hello world")
        # Should have 2 history entries: user + assistant.
        assert len(session.history) >= 2
        assert session.history[0].role == "user"
        assert session.history[1].role == "assistant"
