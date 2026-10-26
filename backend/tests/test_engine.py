"""Comprehensive tests for the conversation engine (FSM)."""

import pytest
from datetime import datetime

from app.brain.engine import ConversationEngine, ConversationSession
from app.brain.states import ConversationState

# Fixed reference: Wednesday 2025-01-15 10:00
REF = datetime(2025, 1, 15, 10, 0, 0)


def make_engine() -> tuple[ConversationEngine, str]:
    """Create an engine with a fixed reference date and start a session."""
    engine = ConversationEngine(reference_date=REF)
    sid = engine.create_session()
    return engine, sid


# ===================================================================
# Session management
# ===================================================================

class TestSessionManagement:

    def test_create_session_returns_id(self):
        engine = ConversationEngine(reference_date=REF)
        sid = engine.create_session()
        assert isinstance(sid, str)
        assert len(sid) > 0

    def test_create_session_with_custom_id(self):
        engine = ConversationEngine(reference_date=REF)
        sid = engine.create_session("my-custom-id")
        assert sid == "my-custom-id"

    def test_get_session(self):
        engine = ConversationEngine(reference_date=REF)
        sid = engine.create_session()
        session = engine.get_session(sid)
        assert session is not None
        assert session.session_id == sid

    def test_get_unknown_session(self):
        engine = ConversationEngine(reference_date=REF)
        assert engine.get_session("nonexistent") is None

    def test_process_unknown_session_raises(self):
        engine = ConversationEngine(reference_date=REF)
        with pytest.raises(ValueError):
            engine.process_input("nonexistent", "hello")


# ===================================================================
# Greeting & start
# ===================================================================

class TestGreeting:

    def test_start_conversation_returns_greeting(self):
        engine, sid = make_engine()
        resp = engine.start_conversation(sid)
        assert "Golden Fork" in resp.message
        assert resp.state == "ask_date"

    def test_greeting_state_advances_on_any_input(self):
        engine, sid = make_engine()
        # Don't start conversation, session is in GREETING state
        resp = engine.process_input(sid, "hello")
        # Should advance past greeting
        assert resp.state == "ask_date"

    def test_greeting_with_entities_skips_ahead(self):
        engine, sid = make_engine()
        resp = engine.process_input(sid, "I want a table for 4 tomorrow at 7pm")
        # All entities provided → should jump to confirm
        assert resp.state == "confirm"
        assert resp.collected_data["date"] == "2025-01-16"
        assert resp.collected_data["time"] == "19:00"
        assert resp.collected_data["party_size"] == 4


# ===================================================================
# Happy path — step by step
# ===================================================================

class TestHappyPath:

    def test_full_conversation(self):
        engine, sid = make_engine()

        # Start
        resp = engine.start_conversation(sid)
        assert resp.state == "ask_date"

        # Provide date
        resp = engine.process_input(sid, "tomorrow")
        assert resp.state == "ask_time"
        assert resp.collected_data["date"] == "2025-01-16"

        # Provide time
        resp = engine.process_input(sid, "7pm")
        assert resp.state == "ask_party_size"
        assert resp.collected_data["time"] == "19:00"

        # Provide party size
        resp = engine.process_input(sid, "4 people")
        assert resp.state == "confirm"
        assert resp.collected_data["party_size"] == 4

        # Confirm
        resp = engine.process_input(sid, "yes")
        assert resp.state == "completed"
        assert "confirmed" in resp.message.lower()

    def test_all_info_at_once(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)

        resp = engine.process_input(sid, "table for 4 tomorrow at 7pm")
        assert resp.state == "confirm"

        resp = engine.process_input(sid, "book it")
        assert resp.state == "completed"


# ===================================================================
# Missing information
# ===================================================================

class TestMissingInfo:

    def test_no_date_reprompts(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)

        resp = engine.process_input(sid, "I want to book")
        assert resp.state == "ask_date"
        assert "date" in resp.message.lower()

    def test_no_time_reprompts(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)

        engine.process_input(sid, "tomorrow")
        resp = engine.process_input(sid, "hmm let me think")
        assert resp.state == "ask_time"
        assert "time" in resp.message.lower()

    def test_no_party_size_reprompts(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)

        engine.process_input(sid, "tomorrow")
        engine.process_input(sid, "7pm")
        resp = engine.process_input(sid, "I'm not sure yet")
        assert resp.state == "ask_party_size"
        assert "guest" in resp.message.lower() or "people" in resp.message.lower()


# ===================================================================
# Invalid input
# ===================================================================

class TestInvalidInput:

    def test_past_date_rejected(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)

        resp = engine.process_input(sid, "2025-01-10")
        assert resp.state == "ask_date"
        assert resp.collected_data == {"date": None, "time": None, "party_size": None}
        assert resp.message == (
            "That date is in the past. Could you please choose a future date?"
        )

    def test_time_outside_hours_rejected(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow")

        resp = engine.process_input(sid, "3am")
        assert resp.state == "ask_time"
        assert "open" in resp.message.lower() or "hour" in resp.message.lower()

    def test_party_size_zero_rejected(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow")
        engine.process_input(sid, "7pm")

        resp = engine.process_input(sid, "0 people")
        assert resp.state == "ask_party_size"
        assert "at least 1" in resp.message.lower()

    def test_party_size_too_large_rejected(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow")
        engine.process_input(sid, "7pm")

        resp = engine.process_input(sid, "50 people")
        assert resp.state == "ask_party_size"
        assert "20" in resp.message

    def test_time_too_late_rejected(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow")

        resp = engine.process_input(sid, "10pm")
        assert resp.state == "ask_time"
        assert "9:30 PM" in resp.message or "open" in resp.message.lower()


# ===================================================================
# Corrections
# ===================================================================

class TestCorrections:

    def test_change_date_clears_and_reprompts(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow")
        engine.process_input(sid, "7pm")
        engine.process_input(sid, "4 people")

        resp = engine.process_input(sid, "change the date")
        assert resp.state == "ask_date"
        assert resp.collected_data["date"] is None

    def test_change_time_clears_and_reprompts(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow")
        engine.process_input(sid, "7pm")
        engine.process_input(sid, "4 people")

        resp = engine.process_input(sid, "change the time")
        assert resp.state == "ask_time"
        assert resp.collected_data["time"] is None

    def test_change_party_size_clears_and_reprompts(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow")
        engine.process_input(sid, "7pm")
        engine.process_input(sid, "4 people")

        resp = engine.process_input(sid, "change the number of people")
        assert resp.state == "ask_party_size"
        assert resp.collected_data["party_size"] is None

    def test_change_date_with_value(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow")
        engine.process_input(sid, "7pm")
        engine.process_input(sid, "4 people")
        # Now in CONFIRM

        resp = engine.process_input(sid, "change the date to friday")
        # Should update date and re-confirm
        assert resp.collected_data["date"] == "2025-01-17"
        assert resp.state == "confirm"

    def test_implicit_correction_during_confirm(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow at 7pm for 4")

        # Now in confirm, provide a different party size
        resp = engine.process_input(sid, "actually 6 people")
        assert resp.collected_data["party_size"] == 6
        assert resp.state == "confirm"

    def test_deny_in_confirm_asks_what_to_change(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow at 7pm for 4")

        resp = engine.process_input(sid, "no")
        assert resp.state == "confirm"
        assert "change" in resp.message.lower()


# ===================================================================
# Cancel & restart
# ===================================================================

class TestCancelRestart:

    def test_cancel_from_ask_date(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)

        resp = engine.process_input(sid, "cancel")
        assert resp.state == "cancelled"

    def test_cancel_from_confirm(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow at 7pm for 4")

        resp = engine.process_input(sid, "cancel")
        assert resp.state == "cancelled"

    def test_restart_from_ask_time(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow")

        resp = engine.process_input(sid, "start over")
        assert resp.state == "ask_date"
        assert resp.collected_data["date"] is None
        assert resp.collected_data["time"] is None
        assert resp.collected_data["party_size"] is None

    def test_restart_from_confirm(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow at 7pm for 4")

        resp = engine.process_input(sid, "restart")
        assert resp.state == "ask_date"
        assert resp.collected_data == {"date": None, "time": None, "party_size": None}

    def test_input_after_cancel_stays_cancelled(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "cancel")

        resp = engine.process_input(sid, "hello")
        assert resp.state == "cancelled"

    def test_restart_after_cancel(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "cancel")

        resp = engine.process_input(sid, "start over")
        assert resp.state == "ask_date"

    def test_input_after_completed_stays_completed(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow at 7pm for 4")
        engine.process_input(sid, "yes")

        resp = engine.process_input(sid, "hello")
        assert resp.state == "completed"

    def test_restart_after_completed(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow at 7pm for 4")
        engine.process_input(sid, "yes")

        resp = engine.process_input(sid, "start over")
        assert resp.state == "ask_date"


# ===================================================================
# Help
# ===================================================================

class TestHelp:

    def test_help_from_any_state(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)

        resp = engine.process_input(sid, "help")
        assert "date" in resp.message.lower()
        assert "time" in resp.message.lower()
        # State shouldn't change
        assert resp.state == "ask_date"

    def test_help_during_confirm(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow at 7pm for 4")

        resp = engine.process_input(sid, "what can you do")
        assert "help" in resp.message.lower() or "date" in resp.message.lower()


# ===================================================================
# Context-aware bare numbers
# ===================================================================

class TestContextAwareBareNumbers:

    def test_bare_number_as_party_size(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow")
        engine.process_input(sid, "7pm")

        resp = engine.process_input(sid, "4")
        assert resp.collected_data["party_size"] == 4
        assert resp.state == "confirm"

    def test_bare_number_as_time(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow")

        resp = engine.process_input(sid, "7")
        # Should interpret 7 as 7PM (19:00) in time context
        assert resp.collected_data["time"] == "19:00"
        assert resp.state == "ask_party_size"


# ===================================================================
# Edge cases
# ===================================================================

class TestEdgeCases:

    def test_multiple_sessions_independent(self):
        engine = ConversationEngine(reference_date=REF)
        sid1 = engine.create_session()
        sid2 = engine.create_session()

        engine.start_conversation(sid1)
        engine.start_conversation(sid2)

        engine.process_input(sid1, "tomorrow")
        resp2 = engine.process_input(sid2, "friday at 8pm for 2")

        s1 = engine.get_session(sid1)
        s2 = engine.get_session(sid2)

        assert s1.date == "2025-01-16"
        assert s1.time is None  # only date provided
        assert s2.date == "2025-01-17"
        assert s2.time == "20:00"
        assert s2.party_size == 2

    def test_conversation_history_recorded(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow")

        session = engine.get_session(sid)
        # Should have at least the greeting + "tomorrow" turn
        assert len(session.history) >= 2

    def test_collected_data_dict(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow at 7pm for 4")

        session = engine.get_session(sid)
        data = session.collected_data()
        assert data == {
            "date": "2025-01-16",
            "time": "19:00",
            "party_size": 4,
        }

    def test_confirm_with_unrelated_input(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)
        engine.process_input(sid, "tomorrow at 7pm for 4")

        resp = engine.process_input(sid, "what is the weather like")
        assert resp.state == "confirm"
        assert "confirm" in resp.message.lower() or "yes" in resp.message.lower()

    def test_party_size_word_and_date(self):
        engine, sid = make_engine()
        engine.start_conversation(sid)

        resp = engine.process_input(sid, "tomorrow for three")
        assert resp.collected_data["date"] == "2025-01-16"
        assert resp.collected_data["party_size"] == 3
        assert resp.state == "ask_time"
