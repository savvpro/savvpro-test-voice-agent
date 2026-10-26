"""Tests for intent classification."""

import pytest
from brain.intents import Intent, classify


class TestGreetingIntent:
    """Greeting detection tests."""

    @pytest.mark.parametrize("text", [
        "hello", "hi", "hey", "good morning", "good evening",
    ])
    def test_greetings(self, text):
        assert Intent.GREETING in classify(text)


class TestBookingIntent:
    """Booking-related intent tests."""

    @pytest.mark.parametrize("text", [
        "I'd like to book a table",
        "make a reservation",
        "book a table please",
    ])
    def test_booking_keywords(self, text):
        intents = classify(text)
        assert Intent.BOOK in intents or Intent.PROVIDE_DATE in intents


class TestDateIntent:
    """Date provision tests."""

    @pytest.mark.parametrize("text", [
        "tomorrow",
        "this friday",
        "next saturday",
        "January 15",
        "12/25",
    ])
    def test_date_patterns(self, text):
        assert Intent.PROVIDE_DATE in classify(text)


class TestTimeIntent:
    """Time provision tests."""

    @pytest.mark.parametrize("text", [
        "at 7pm",
        "7:30 pm",
        "around 8",
        "noon",
        "at 6:00",
    ])
    def test_time_patterns(self, text):
        assert Intent.PROVIDE_TIME in classify(text)


class TestPartySizeIntent:
    """Party size detection tests."""

    @pytest.mark.parametrize("text", [
        "for 4",
        "party of 6",
        "2 people",
        "just me",
        "table for two",
    ])
    def test_party_size_patterns(self, text):
        assert Intent.PROVIDE_PARTY_SIZE in classify(text)


class TestConfirmDeny:
    """Confirmation and denial tests."""

    @pytest.mark.parametrize("text", [
        "yes", "yeah", "sure", "sounds good", "confirm",
    ])
    def test_confirm(self, text):
        assert Intent.CONFIRM in classify(text)

    @pytest.mark.parametrize("text", [
        "no", "nope", "nah", "wrong",
    ])
    def test_deny(self, text):
        assert Intent.DENY in classify(text)


class TestCancelIntent:
    """Cancel intent tests."""

    @pytest.mark.parametrize("text", [
        "cancel", "nevermind", "forget it", "abort",
    ])
    def test_cancel(self, text):
        assert Intent.CANCEL in classify(text)


class TestChangeIntent:
    """Change/modify intent tests."""

    @pytest.mark.parametrize("text", [
        "I want to change the time",
        "can we switch the date",
        "actually, make it 8pm",
    ])
    def test_change(self, text):
        intents = classify(text)
        assert Intent.CHANGE in intents


class TestMultiIntent:
    """Multi-intent detection tests."""

    def test_date_and_time(self):
        intents = classify("tomorrow at 7pm")
        assert Intent.PROVIDE_DATE in intents
        assert Intent.PROVIDE_TIME in intents

    def test_date_time_party(self):
        intents = classify("book a table for 4 tomorrow at 7pm")
        assert Intent.PROVIDE_DATE in intents
        assert Intent.PROVIDE_TIME in intents
        assert Intent.PROVIDE_PARTY_SIZE in intents

    def test_unknown_fallback(self):
        intents = classify("asdfghjkl")
        assert Intent.UNKNOWN in intents
