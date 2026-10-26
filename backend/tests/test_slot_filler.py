"""Tests for the slot filler and expanded session model.

Covers:
- SlotMap defaults, reset_date_slots, reset_action_slots.
- fill_from_turn: tracking ID extraction, ambiguous IDs, phone extraction,
  date/period extraction, date rejections.
- missing_required_slots per state.
- DialogueState enum values.
- Session model fields.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.brain.normalizer import normalize
from app.brain.slot_filler import (
    fill_from_turn,
    missing_required_slots,
    reset_action_slots,
    reset_date_slots,
)
from app.models.session import (
    DecisionTrace,
    DialogueState,
    Session,
    SlotMap,
    Turn,
)

CLOCK = datetime(2026, 10, 26, 14, 30, tzinfo=timezone(timedelta(hours=5), name="PKT"))


# ── SlotMap defaults ──────────────────────────────────────────────────


class TestSlotMapDefaults:
    def test_all_none(self):
        sm = SlotMap()
        assert sm.tracking_id is None
        assert sm.ambiguous_ids == []
        assert sm.phone_last4 is None
        assert sm.intended_date is None
        assert sm.intended_period is None
        assert sm.confirmed_slot_id is None
        assert sm.pickup_point_id is None
        assert sm.action_intent is None
        assert sm.cancel_confirmed is False
        assert sm.verified is False


# ── Reset helpers ─────────────────────────────────────────────────────


class TestResetHelpers:
    def test_reset_date_slots(self):
        sm = SlotMap(
            intended_date=date(2026, 10, 27),
            intended_period="morning",
            confirmed_slot_id="slot-1",
        )
        reset_date_slots(sm)
        assert sm.intended_date is None
        assert sm.intended_period is None
        assert sm.confirmed_slot_id is None

    def test_reset_action_slots(self):
        sm = SlotMap(
            action_intent="reschedule",
            intended_date=date(2026, 10, 27),
            intended_period="morning",
            confirmed_slot_id="slot-1",
            pickup_point_id="PP-001",
            cancel_confirmed=True,
        )
        reset_action_slots(sm)
        assert sm.action_intent is None
        assert sm.intended_date is None
        assert sm.intended_period is None
        assert sm.confirmed_slot_id is None
        assert sm.pickup_point_id is None
        assert sm.cancel_confirmed is False

    def test_reset_action_preserves_tracking(self):
        sm = SlotMap(tracking_id="RD12345678", verified=True)
        reset_action_slots(sm)
        assert sm.tracking_id == "RD12345678"
        assert sm.verified is True


# ── fill_from_turn — tracking ID ─────────────────────────────────────


class TestFillTrackingId:
    def test_single_tracking_id(self):
        sm = SlotMap()
        norm = normalize("my tracking id is rd12345678")
        extracted = fill_from_turn(sm, norm, CLOCK, "COLLECT_TRACKING_ID")
        assert sm.tracking_id == "RD12345678"
        assert "tracking_id" in extracted

    def test_ambiguous_two_ids(self):
        sm = SlotMap()
        norm = normalize("is it rd10000001 or rd20000002")
        extracted = fill_from_turn(sm, norm, CLOCK, "COLLECT_TRACKING_ID")
        assert sm.tracking_id is None  # NOT filled
        assert sm.ambiguous_ids == ["RD10000001", "RD20000002"]
        assert "ambiguous_ids" in extracted

    def test_no_tracking_id(self):
        sm = SlotMap()
        norm = normalize("i want to reschedule")
        extracted = fill_from_turn(sm, norm, CLOCK, "COLLECT_TRACKING_ID")
        assert sm.tracking_id is None
        assert "tracking_id" not in extracted

    def test_tracking_id_in_confirm_state(self):
        """In CONFIRM_TRACKING_ID, a new ID can be extracted (correction)."""
        sm = SlotMap(tracking_id="RD11111111")
        norm = normalize("no it's rd22222222")
        fill_from_turn(sm, norm, CLOCK, "CONFIRM_TRACKING_ID")
        assert sm.tracking_id == "RD22222222"

    def test_tracking_not_extracted_in_wrong_state(self):
        """In VERIFY_PHONE, tracking ID extraction should NOT happen."""
        sm = SlotMap()
        norm = normalize("rd12345678")
        fill_from_turn(sm, norm, CLOCK, "VERIFY_PHONE")
        assert sm.tracking_id is None


# ── fill_from_turn — phone ────────────────────────────────────────────


class TestFillPhone:
    def test_phone_extracted(self):
        sm = SlotMap(tracking_id="RD12345678")
        norm = normalize("my phone ends in 9012")
        extracted = fill_from_turn(sm, norm, CLOCK, "VERIFY_PHONE")
        assert sm.phone_last4 == "9012"
        assert extracted["phone_last4"] == "9012"

    def test_phone_may_overlap_tracking_digits_on_separate_turn(self):
        """A separate phone turn may contain digits from the tracking ID."""
        sm = SlotMap(tracking_id="RD12345678")
        norm = normalize("3456")
        fill_from_turn(sm, norm, CLOCK, "VERIFY_PHONE")
        assert sm.phone_last4 == "3456"

    def test_phone_not_extracted_in_wrong_state(self):
        sm = SlotMap(tracking_id="RD12345678")
        norm = normalize("1234")
        fill_from_turn(sm, norm, CLOCK, "COLLECT_DATE")
        assert sm.phone_last4 is None


# ── fill_from_turn — date/period ──────────────────────────────────────


class TestFillDatePeriod:
    def test_date_and_period(self):
        sm = SlotMap()
        norm = normalize("tomorrow morning")
        fill_from_turn(sm, norm, CLOCK, "COLLECT_DATE")
        assert sm.intended_date == date(2026, 10, 27)
        assert sm.intended_period == "morning"

    def test_date_only(self):
        sm = SlotMap()
        norm = normalize("tomorrow")
        fill_from_turn(sm, norm, CLOCK, "COLLECT_DATE")
        assert sm.intended_date == date(2026, 10, 27)
        assert sm.intended_period is None

    def test_period_only_in_collect_period(self):
        sm = SlotMap(intended_date=date(2026, 10, 27))
        norm = normalize("evening please")
        fill_from_turn(sm, norm, CLOCK, "COLLECT_PERIOD")
        assert sm.intended_period == "evening"

    def test_date_rejected_past(self):
        sm = SlotMap()
        norm = normalize("in 10 days")
        extracted = fill_from_turn(sm, norm, CLOCK, "COLLECT_DATE")
        assert sm.intended_date is None  # Not set on rejection
        assert "date_rejection" in extracted
        assert extracted["date_rejection"] == "out_of_range"

    def test_date_cutoff(self):
        sm = SlotMap()
        norm = normalize("today morning")
        extracted = fill_from_turn(sm, norm, CLOCK, "COLLECT_DATE")
        # Morning at 14:30 → cutoff
        assert sm.intended_date is None  # cutoff means date isn't set either
        assert "period_cutoff" in extracted

    def test_date_not_extracted_in_wrong_state(self):
        sm = SlotMap()
        norm = normalize("tomorrow morning")
        fill_from_turn(sm, norm, CLOCK, "VERIFY_PHONE")
        assert sm.intended_date is None
        assert sm.intended_period is None


# ── missing_required_slots ────────────────────────────────────────────


class TestMissingSlots:
    def test_tracking_missing(self):
        sm = SlotMap()
        assert "tracking_id" in missing_required_slots(sm, "COLLECT_TRACKING_ID")

    def test_tracking_present(self):
        sm = SlotMap(tracking_id="RD12345678")
        assert missing_required_slots(sm, "COLLECT_TRACKING_ID") == []

    def test_phone_missing(self):
        sm = SlotMap()
        assert "phone_last4" in missing_required_slots(sm, "VERIFY_PHONE")

    def test_date_missing(self):
        sm = SlotMap()
        assert "intended_date" in missing_required_slots(sm, "COLLECT_DATE")

    def test_period_missing(self):
        sm = SlotMap(intended_date=date(2026, 10, 27))
        assert "intended_period" in missing_required_slots(sm, "COLLECT_PERIOD")

    def test_pickup_missing(self):
        sm = SlotMap()
        assert "pickup_point_id" in missing_required_slots(sm, "COLLECT_PICKUP_POINT")


# ── DialogueState enum ────────────────────────────────────────────────


class TestDialogueState:
    def test_all_14_states(self):
        assert len(DialogueState) == 14

    def test_greeting(self):
        assert DialogueState.GREETING.value == "GREETING"

    def test_end(self):
        assert DialogueState.END.value == "END"

    def test_anything_else(self):
        assert DialogueState.ANYTHING_ELSE.value == "ANYTHING_ELSE"


# ── Session model ─────────────────────────────────────────────────────


class TestSessionModel:
    def test_defaults(self):
        s = Session(session_id="test-1", created_at=CLOCK)
        assert s.state == DialogueState.GREETING
        assert s.ended is False
        assert s.silence_count == 0
        assert s.unknown_count == 0
        assert s.tracking_attempts == 0
        assert s.phone_attempts == 0
        assert s.last_assistant_reply == ""
        assert s.history == []

    def test_slots_default(self):
        s = Session(session_id="test-2", created_at=CLOCK)
        assert isinstance(s.slots, SlotMap)
        assert s.slots.tracking_id is None

    def test_has_lock(self):
        s = Session(session_id="test-3", created_at=CLOCK)
        assert hasattr(s, "lock")


# ── Turn and DecisionTrace ────────────────────────────────────────────


class TestTurnAndTrace:
    def test_turn_creation(self):
        t = Turn(role="user", text="hello")
        assert t.role == "user"
        assert t.trace is None

    def test_trace_creation(self):
        trace = DecisionTrace(
            intent="reschedule",
            intent_confidence=0.85,
            state_before="CHOOSE_ACTION",
            state_after="COLLECT_DATE",
        )
        assert trace.intent == "reschedule"
        assert trace.intent_confidence == 0.85

    def test_turn_with_trace(self):
        trace = DecisionTrace(intent="affirm", intent_confidence=1.0)
        t = Turn(role="assistant", text="Booked!", trace=trace)
        assert t.trace is not None
        assert t.trace.intent == "affirm"
