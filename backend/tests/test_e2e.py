"""
Phase 7: End-to-End Integration and Messy Caller Stress Tests.

Simulates complex, chaotic caller interactions:
1. Multi-slot simultaneous utterance ("book Tuesday at 5pm with Dr. Khan for John")
2. Immediate slot correction ("Wait, my name is Sara, not Susan")
3. Late-stage in-CONFIRM slot overhaul ("Actually change the time to 10am and switch to Dr. Patel")
4. Disorganized rambling and filler words ("Um uh well basically I have a severe toothache")
5. Cancellation flow
6. Rescheduling flow
7. 3-strikes unclear fallback to human staff handover
"""

import pytest
from brain.fsm import ConversationState, FSMState, handle_utterance, initial_state


class TestFullEndToEndScenarios:
    def test_e2e_multi_slot_booking_with_confirmation(self):
        """Caller provides almost all information upfront."""
        _, state = initial_state()

        # Caller says: "Hi, I need an appointment for John Smith with Dr. Khan on Monday at 3pm"
        reply, state = handle_utterance(
            "Hi, I need an appointment for John Smith with Dr. Khan on Monday at 3pm",
            state
        )

        assert state.slots.get("name") == "John Smith"
        assert state.slots.get("doctor") == "Dr. Khan"
        assert state.slots.get("time") == "15:00"
        assert "date" in state.slots

        # Reason was not provided yet, so agent should ask for reason
        assert state.fsm_state == FSMState.COLLECT_REASON

        # Caller gives reason: "Routine cleaning"
        reply, state = handle_utterance("Just a routine cleaning", state)

        # Brain checks availability and transitions to CONFIRM
        assert state.fsm_state == FSMState.CONFIRM
        assert "John Smith" in reply
        assert "Dr. Khan" in reply

        # Caller confirms
        reply, state = handle_utterance("Yes, that's perfect", state)
        assert state.fsm_state == FSMState.END
        assert "booked" in reply.lower()

    def test_e2e_messy_caller_with_multiple_corrections(self):
        """
        Messy caller:
        1. Gives wrong name, corrects it.
        2. Picks Dr. Khan, then in date step changes mind to Dr. Smith.
        3. Reaches confirm, changes date and time.
        4. Confirms final details.
        """
        _, state = initial_state()

        # Step 1: Request
        _, state = handle_utterance("Can I schedule a visit please?", state)
        assert state.fsm_state == FSMState.COLLECT_NAME

        # Step 2: Name with hesitation
        _, state = handle_utterance("Uh, Susan", state)
        assert state.slots.get("name") == "Susan"

        # Step 3: Immediate name correction
        reply, state = handle_utterance("Actually my name is Sara, sorry", state)
        assert state.slots.get("name") == "Sara"
        assert state.fsm_state == FSMState.COLLECT_DOCTOR

        # Step 4: Doctor
        _, state = handle_utterance("Dr. Khan", state)
        assert state.slots.get("doctor") == "Dr. Khan"
        assert state.fsm_state == FSMState.COLLECT_DATE

        # Step 5: Mid-flow correction (change doctor while asked for date)
        reply, state = handle_utterance("Actually switch to Dr. Smith instead", state)
        assert state.slots.get("doctor") == "Dr. Smith"
        assert state.fsm_state == FSMState.COLLECT_DATE
        assert "date" in reply.lower() or "updated" in reply.lower()

        # Step 6: Provide Date
        _, state = handle_utterance("Tomorrow", state)
        assert "date" in state.slots
        assert state.fsm_state == FSMState.COLLECT_TIME

        # Step 7: Provide Time
        _, state = handle_utterance("3pm", state)
        assert state.slots.get("time") == "15:00"
        assert state.fsm_state == FSMState.COLLECT_REASON

        # Step 8: Provide Reason
        _, state = handle_utterance("Toothache", state)
        assert state.fsm_state == FSMState.CONFIRM

        # Step 9: In-CONFIRM correction for both time and date
        reply, state = handle_utterance("Actually make it Monday at 10am instead", state)
        assert state.fsm_state == FSMState.CONFIRM
        assert state.slots.get("time") == "10:00"
        assert "10:00" in reply or "10" in reply

        # Step 10: Final Confirmation
        reply, state = handle_utterance("Looks great, confirm it", state)
        assert state.fsm_state == FSMState.END
        assert "booked" in reply.lower()

    def test_e2e_reschedule_flow(self):
        """Caller reschedules existing appointment."""
        _, state = initial_state()

        # Caller wants to reschedule
        reply, state = handle_utterance("I need to reschedule my visit", state)
        assert state.fsm_state == FSMState.RESCHEDULE_LOOKUP

        # Provides name
        reply, state = handle_utterance("Sara Connor", state)
        assert state.slots.get("name") == "Sara Connor"
        assert state.fsm_state == FSMState.RESCHEDULE_COLLECT_DATE

        # Provides new date
        reply, state = handle_utterance("Next Tuesday", state)
        assert "date" in state.slots
        assert state.fsm_state in (FSMState.COLLECT_TIME, FSMState.RESCHEDULE_COLLECT_TIME)

        # Provides new time
        reply, state = handle_utterance("10am", state)
        assert state.slots.get("time") == "10:00"

    def test_e2e_cancel_flow(self):
        """Caller cancels appointment."""
        _, state = initial_state()

        # Request cancellation
        reply, state = handle_utterance("I would like to cancel my booking", state)
        assert state.fsm_state == FSMState.CANCEL_LOOKUP

        # Give name
        reply, state = handle_utterance("John Smith", state)
        assert state.fsm_state == FSMState.CANCEL_CONFIRM
        assert "John Smith" in reply

        # Confirm cancellation
        reply, state = handle_utterance("Yes, please cancel it", state)
        assert state.fsm_state == FSMState.END
        assert "cancelled" in reply.lower()

    def test_e2e_consecutive_unclear_handover(self):
        """Repeated unintelligible utterances trigger staff escalation."""
        _, state = initial_state()
        _, state = handle_utterance("book an appointment", state)

        # 3 garbage utterances
        r1, state = handle_utterance("asdfghjkl", state)
        assert state.unclear_count == 1
        assert state.fsm_state != FSMState.END

        r2, state = handle_utterance("qwertyuiop", state)
        assert state.unclear_count == 2
        assert state.fsm_state != FSMState.END

        r3, state = handle_utterance("zxcvbnm", state)
        assert state.fsm_state == FSMState.END
        assert "difficulty" in r3.lower() or "staff" in r3.lower()

