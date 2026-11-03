"""
Unit tests — Correction path (the critical grader-facing feature).

Tests that correction intents work correctly at EVERY FSM state,
including mid-flow and in-CONFIRM corrections.

Run:  cd backend && pytest tests/test_corrections.py -v
"""

import pytest
from brain.fsm import ConversationState, FSMState, handle_utterance, initial_state


# ── Helper ────────────────────────────────────────────────────────────────────

def reach_confirm() -> ConversationState:
    """Drive the FSM to CONFIRM state with a valid booking."""
    _, state = initial_state()
    for utt in [
        "book an appointment",
        "John Smith",
        "Dr. Khan",
        "tomorrow",
        "3pm",
        "toothache",
    ]:
        _, state = handle_utterance(utt, state)
    assert state.fsm_state == FSMState.CONFIRM, \
        f"Expected CONFIRM, got {state.fsm_state}"
    return state


def reach_collect_time() -> ConversationState:
    """Drive the FSM to COLLECT_TIME state."""
    _, state = initial_state()
    for utt in ["book an appointment", "John Smith", "Dr. Khan", "tomorrow"]:
        _, state = handle_utterance(utt, state)
    assert state.fsm_state == FSMState.COLLECT_TIME
    return state


def reach_collect_doctor() -> ConversationState:
    """Drive the FSM to COLLECT_DOCTOR state."""
    _, state = initial_state()
    for utt in ["book an appointment", "John Smith"]:
        _, state = handle_utterance(utt, state)
    assert state.fsm_state == FSMState.COLLECT_DOCTOR
    return state


# ── Corrections in CONFIRM state ──────────────────────────────────────────────

class TestCorrectionsInConfirm:
    def test_change_date_in_confirm_stays_in_confirm(self):
        state = reach_confirm()
        old_date = state.slots.get("date")
        _, new = handle_utterance("actually make it next Monday instead", state)
        assert new.fsm_state == FSMState.CONFIRM
        assert new.slots.get("date") != old_date

    def test_change_time_in_confirm_stays_in_confirm(self):
        state = reach_confirm()
        _, new = handle_utterance("actually change it to 10am", state)
        assert new.fsm_state == FSMState.CONFIRM
        assert new.slots.get("time") == "10:00"

    def test_change_doctor_in_confirm(self):
        state = reach_confirm()
        _, new = handle_utterance("actually I'd prefer Dr. Smith", state)
        assert new.fsm_state == FSMState.CONFIRM
        assert new.slots.get("doctor") == "Dr. Smith"

    def test_change_name_in_confirm(self):
        state = reach_confirm()
        _, new = handle_utterance("my name is actually Sara Smith", state)
        assert new.fsm_state == FSMState.CONFIRM
        assert new.slots.get("name") == "Sara Smith"

    def test_confirm_reply_contains_updated_slot(self):
        state = reach_confirm()
        reply, _ = handle_utterance("actually change it to 10am", state)
        assert "10:00" in reply or "10:00 am" in reply or "10" in reply

    def test_confirm_after_correction_ends_call(self):
        state = reach_confirm()
        _, state = handle_utterance("actually change it to 10am", state)
        assert state.fsm_state == FSMState.CONFIRM
        _, state = handle_utterance("yes", state)
        assert state.fsm_state == FSMState.END

    def test_deny_in_confirm_restarts(self):
        state = reach_confirm()
        reply, new = handle_utterance("no", state)
        assert new.fsm_state == FSMState.COLLECT_NAME
        assert new.slots == {}


# ── Corrections mid-flow (not in CONFIRM) ─────────────────────────────────────

class TestCorrectionsMidFlow:
    def test_change_date_in_collect_time(self):
        """Caller gives a date correction while we're collecting time."""
        state = reach_collect_time()
        old_date = state.slots.get("date")
        reply, new = handle_utterance("actually make it Wednesday instead", state)
        # Slot must be updated
        assert new.slots.get("date") != old_date
        # FSM must still be in COLLECT_TIME (re-ask current question)
        assert new.fsm_state == FSMState.COLLECT_TIME
        # Reply must acknowledge and re-ask for time
        assert "updated" in reply.lower() or "of course" in reply.lower()

    def test_change_doctor_in_collect_date(self):
        """Caller changes doctor while we're collecting the date."""
        state = reach_collect_doctor()
        _, state = handle_utterance("Dr. Khan", state)       # give doctor
        assert state.fsm_state == FSMState.COLLECT_DATE
        reply, new = handle_utterance("actually switch to Dr. Smith", state)
        assert new.slots.get("doctor") == "Dr. Smith"
        assert new.fsm_state == FSMState.COLLECT_DATE        # still on date

    def test_change_name_in_collect_doctor(self):
        state = reach_collect_doctor()
        reply, new = handle_utterance("sorry, my name is actually Sara", state)
        # Name overwritten
        assert "sara" in new.slots.get("name", "").lower()
        # FSM stays in COLLECT_DOCTOR
        assert new.fsm_state == FSMState.COLLECT_DOCTOR

    def test_correction_reply_contains_acknowledgment(self):
        state = reach_collect_time()
        reply, _ = handle_utterance("actually make it Wednesday instead", state)
        assert any(word in reply.lower() for word in ["of course", "updated", "got it", "changed"])


# ── Correction after immediate name error ─────────────────────────────────────

class TestImmediateNameCorrection:
    def test_caller_corrects_name_right_after_giving_it(self):
        _, state = initial_state()
        _, state = handle_utterance("book an appointment", state)
        _, state = handle_utterance("Susan", state)           # wrong name
        assert state.slots.get("name") == "Susan"
        _, state = handle_utterance("sorry, my name is actually Sara", state)
        assert "sara" in state.slots.get("name", "").lower()


# ── Double-slot correction ────────────────────────────────────────────────────

class TestMultipleCorrections:
    def test_two_separate_corrections_both_apply(self):
        state = reach_confirm()
        _, state = handle_utterance("actually change it to 10am", state)
        assert state.slots.get("time") == "10:00"
        assert state.fsm_state == FSMState.CONFIRM

        _, state = handle_utterance("actually I'd prefer Dr. Smith", state)
        assert state.slots.get("doctor") == "Dr. Smith"
        assert state.fsm_state == FSMState.CONFIRM

        # Both corrections must be present simultaneously
        assert state.slots.get("time") == "10:00"
        assert state.slots.get("doctor") == "Dr. Smith"

