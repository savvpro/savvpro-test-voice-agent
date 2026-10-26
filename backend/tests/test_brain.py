"""Tests for the dialog engine (brain)."""

import pytest
from brain.engine import DialogEngine
from models.conversation import ConversationState


class TestDialogEngine:
    """End-to-end dialog flow tests."""

    def setup_method(self):
        self.engine = DialogEngine()

    def test_start_conversation(self):
        conv_id, greeting, state = self.engine.start_conversation()
        assert conv_id
        assert "Welcome" in greeting
        assert state["state"] == ConversationState.ASK_DATE.value

    def test_full_booking_flow(self):
        """Test a complete happy-path booking."""
        conv_id, greeting, state = self.engine.start_conversation()

        # Provide date
        response, state = self.engine.process(conv_id, "tomorrow")
        assert state["state"] in (
            ConversationState.ASK_TIME.value,
            ConversationState.ASK_PARTY_SIZE.value,
        )

        # Provide time
        response, state = self.engine.process(conv_id, "at 6pm")
        assert state["state"] in (
            ConversationState.ASK_PARTY_SIZE.value,
            ConversationState.ASK_NAME.value,
        )

        # Provide party size
        response, state = self.engine.process(conv_id, "4 people")
        assert state["state"] in (
            ConversationState.ASK_NAME.value,
            ConversationState.CONFIRM.value,
        )

        # Provide name
        response, state = self.engine.process(conv_id, "My name is John")
        assert state["state"] in (
            ConversationState.CONFIRM.value,
            ConversationState.BOOKED.value,
        )

        # Confirm booking
        if state["state"] == ConversationState.CONFIRM.value:
            response, state = self.engine.process(conv_id, "yes")
            assert state["state"] == ConversationState.BOOKED.value

        assert state["booking"]["status"] == "confirmed"

    def test_cancel_mid_flow(self):
        """Test cancellation during booking process."""
        conv_id, _, _ = self.engine.start_conversation()
        self.engine.process(conv_id, "tomorrow")

        response, state = self.engine.process(conv_id, "cancel")
        assert state["state"] == ConversationState.CANCELLED.value
        assert "cancel" in response.lower()

    def test_invalid_date_past(self):
        """Test rejection of past dates."""
        conv_id, _, _ = self.engine.start_conversation()
        response, state = self.engine.process(conv_id, "January 1 2020")
        # Should either reject or stay in ASK_DATE
        assert state["booking"]["date"] is None or state["state"] == ConversationState.ASK_DATE.value

    def test_invalid_time_outside_hours(self):
        """Test rejection of times outside operating hours."""
        conv_id, _, _ = self.engine.start_conversation()
        self.engine.process(conv_id, "tomorrow")
        response, state = self.engine.process(conv_id, "at 3am")
        assert "open" in response.lower() or state["booking"]["time"] is None

    def test_party_size_too_large(self):
        """Test rejection of party sizes exceeding capacity."""
        conv_id, _, _ = self.engine.start_conversation()
        self.engine.process(conv_id, "tomorrow")
        self.engine.process(conv_id, "6pm")
        response, state = self.engine.process(conv_id, "50 people")
        assert state["booking"]["party_size"] is None

    def test_help_intent(self):
        """Test help response from any state."""
        conv_id, _, _ = self.engine.start_conversation()
        response, _ = self.engine.process(conv_id, "help")
        assert "help" in response.lower() or "open" in response.lower()

    def test_multi_slot_input(self):
        """Test providing multiple pieces of info at once."""
        conv_id, _, _ = self.engine.start_conversation()
        response, state = self.engine.process(
            conv_id, "book a table for 4 tomorrow at 6pm"
        )
        booking = state["booking"]
        # Should have filled multiple slots at once
        assert booking["date"] is not None
        assert booking["time"] is not None
        assert booking["party_size"] == 4

    def test_deny_confirmation(self):
        """Test saying no at confirmation step."""
        conv_id, _, _ = self.engine.start_conversation()
        self.engine.process(conv_id, "tomorrow")
        self.engine.process(conv_id, "6pm")
        self.engine.process(conv_id, "2 people")
        self.engine.process(conv_id, "My name is Jane")

        # Should be at CONFIRM
        conv = self.engine.get_conversation(conv_id)
        if conv.state == ConversationState.CONFIRM:
            response, state = self.engine.process(conv_id, "no")
            assert state["state"] == ConversationState.ASK_DATE.value
            assert "start over" in response.lower() or "prefer" in response.lower()

    def test_restart_after_goodbye(self):
        """Test starting a new booking after completing one."""
        conv_id, _, _ = self.engine.start_conversation()
        self.engine.process(conv_id, "tomorrow")
        self.engine.process(conv_id, "6pm")
        self.engine.process(conv_id, "2")
        self.engine.process(conv_id, "John")

        conv = self.engine.get_conversation(conv_id)
        if conv.state == ConversationState.CONFIRM:
            self.engine.process(conv_id, "yes")

        # Now try to restart
        response, state = self.engine.process(conv_id, "I want to book another table")
        assert "book" in response.lower() or "date" in response.lower()


class TestBookingService:
    """Tests for the booking service."""

    def test_availability_check(self):
        from datetime import date, time, timedelta
        from services.booking import BookingService

        service = BookingService()
        # A random Tuesday should be available
        tuesday = date.today()
        while tuesday.weekday() != 1:
            tuesday += timedelta(days=1)

        assert service.check_availability(tuesday, time(18, 0), 4) is True

    def test_find_alternative(self):
        from datetime import date, time, timedelta
        from services.booking import BookingService

        service = BookingService()
        # Friday 7pm is seeded as fully booked
        friday = date.today()
        while friday.weekday() != 4:
            friday += timedelta(days=1)

        alt = service.find_alternative(friday, time(19, 0), 4)
        # Should suggest an alternative
        assert alt is not None
        alt_date, alt_time = alt
        assert alt_date >= date.today()
