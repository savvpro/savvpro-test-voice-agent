"""
Unit tests — FSM happy-path transitions (brain/fsm.py)

Run:  cd backend && pytest tests/test_fsm.py -v
"""

import pytest
from brain.fsm import ConversationState, FSMState, handle_utterance, initial_state


def make_state(**kwargs) -> ConversationState:
    """Helper: build a ConversationState with slot overrides."""
    s = ConversationState()
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


class TestInitialState:
    def test_greeting_sent(self):
        reply, state = initial_state()
        assert "welcome" in reply.lower() or "hello" in reply.lower()
        assert state.fsm_state == FSMState.GREETING

    def test_greeting_is_idempotent(self):
        r1, _ = initial_state()
        r2, _ = initial_state()
        assert r1 == r2


class TestGreetingState:
    def setup_method(self):
        _, self.state = initial_state()

    def test_book_appointment_transitions_to_collect_name(self):
        _, new = handle_utterance("I'd like to book an appointment", self.state)
        assert new.fsm_state == FSMState.COLLECT_NAME

    def test_reschedule_transitions_to_reschedule_lookup(self):
        _, new = handle_utterance("I need to reschedule", self.state)
        assert new.fsm_state == FSMState.RESCHEDULE_LOOKUP

    def test_cancel_transitions_to_cancel_lookup(self):
        _, new = handle_utterance("cancel my appointment", self.state)
        assert new.fsm_state == FSMState.CANCEL_LOOKUP


class TestHappyPathBooking:
    """Walk through the complete booking flow step by step."""

    def _run_flow(self, utterances: list[str]) -> tuple[str, ConversationState]:
        _, state = initial_state()
        reply = ""
        for utt in utterances:
            reply, state = handle_utterance(utt, state)
        return reply, state

    def test_name_collected(self):
        _, state = initial_state()
        _, state = handle_utterance("book an appointment", state)
        _, state = handle_utterance("John Smith", state)
        assert state.slots.get("name") == "John Smith"

    def test_doctor_collected(self):
        _, state = initial_state()
        _, state = handle_utterance("book an appointment", state)
        _, state = handle_utterance("John Smith", state)
        _, state = handle_utterance("Dr. Khan", state)
        assert state.slots.get("doctor") == "Dr. Khan"

    def test_date_collected(self):
        _, state = initial_state()
        _, state = handle_utterance("book an appointment", state)
        _, state = handle_utterance("John Smith", state)
        _, state = handle_utterance("Dr. Khan", state)
        _, state = handle_utterance("tomorrow", state)
        assert "date" in state.slots

    def test_reaches_confirm(self):
        _, state = initial_state()
        _, state = handle_utterance("book an appointment", state)
        _, state = handle_utterance("John Smith", state)
        _, state = handle_utterance("Dr. Khan", state)
        _, state = handle_utterance("tomorrow", state)
        _, state = handle_utterance("3pm", state)
        _, state = handle_utterance("toothache", state)   # reason
        assert state.fsm_state == FSMState.CONFIRM

    def test_confirm_ends_call(self):
        _, state = initial_state()
        for utt in ["book an appointment", "John Smith", "Dr. Khan",
                    "tomorrow", "3pm", "toothache"]:
            _, state = handle_utterance(utt, state)
        assert state.fsm_state == FSMState.CONFIRM
        _, state = handle_utterance("yes", state)
        assert state.fsm_state == FSMState.END


class TestMultiSlotUtterance:
    """Caller gives multiple slots in one utterance — FSM must skip past filled states."""

    def test_skips_filled_slots(self):
        _, state = initial_state()
        _, state = handle_utterance("book an appointment", state)
        # Give name + doctor + date + time all at once
        _, state = handle_utterance(
            "I'm John Smith and I'd like to see Dr. Khan on Monday at 2pm", state
        )
        # At minimum, name should be filled; FSM should have advanced
        assert state.fsm_state not in (FSMState.GREETING, FSMState.COLLECT_NAME)


class TestUnclearHandling:
    def test_three_clears_leads_to_end(self):
        _, state = initial_state()
        _, state = handle_utterance("book an appointment", state)

        for _ in range(3):
            reply, state = handle_utterance("xyzzy blerf", state)

        assert state.fsm_state == FSMState.END
        assert "staff" in reply.lower() or "difficulty" in reply.lower()

    def test_unclear_count_resets_on_valid_input(self):
        _, state = initial_state()
        _, state = handle_utterance("book an appointment", state)
        _, state = handle_utterance("xyzzy", state)         # unclear #1
        assert state.unclear_count == 1
        _, state = handle_utterance("John Smith", state)    # valid
        assert state.unclear_count == 0


class TestRepeat:
    def test_repeat_resends_last_reply(self):
        _, state = initial_state()
        _, state = handle_utterance("book an appointment", state)
        reply1, state = handle_utterance("John Smith", state)
        reply2, state = handle_utterance("pardon?", state)
        assert reply1 == reply2


class TestGoodbye:
    def test_goodbye_anywhere_ends_call(self):
        _, state = initial_state()
        _, state = handle_utterance("book an appointment", state)
        _, state = handle_utterance("John Smith", state)
        # Mid-flow goodbye
        _, state = handle_utterance("bye", state)
        assert state.fsm_state == FSMState.END


class TestCancelFlow:
    def test_cancel_happy_path(self):
        _, state = initial_state()
        _, state = handle_utterance("cancel my appointment", state)
        assert state.fsm_state == FSMState.CANCEL_LOOKUP
        _, state = handle_utterance("John Smith", state)
        assert state.fsm_state == FSMState.CANCEL_CONFIRM
        _, state = handle_utterance("yes", state)
        assert state.fsm_state == FSMState.END


class TestRescheduleFlow:
    def test_reschedule_name_lookup(self):
        _, state = initial_state()
        _, state = handle_utterance("I need to reschedule", state)
        assert state.fsm_state == FSMState.RESCHEDULE_LOOKUP
        _, state = handle_utterance("Sara Lee", state)
        assert state.fsm_state == FSMState.RESCHEDULE_COLLECT_DATE
        assert state.slots.get("name") == "Sara Lee"

