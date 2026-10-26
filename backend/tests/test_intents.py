"""Tests for the intent classifier."""

from backend.brain.intents import classify, top_intent


def _intent(text):
    return top_intent(text).name


class TestControlIntents:
    def test_greeting(self):
        assert _intent("hi") == "greeting"
        assert _intent("hello") == "greeting"
        assert _intent("hey") == "greeting"
        assert _intent("howdy") == "greeting"
        assert _intent("good morning") == "greeting"

    def test_goodbye(self):
        assert _intent("bye") == "goodbye"
        assert _intent("goodbye") == "goodbye"
        assert _intent("that's all") == "goodbye"
        assert _intent("I'm done") == "goodbye"

    def test_cancel(self):
        assert _intent("cancel") == "cancel"
        assert _intent("never mind") == "cancel"
        assert _intent("forget it") == "cancel"
        assert _intent("don't book") == "cancel"

    def test_help(self):
        assert _intent("help") == "help"
        assert _intent("what can you do") == "help"


class TestConfirmationIntents:
    def test_confirm(self):
        assert _intent("yes") == "confirm"
        assert _intent("yeah") == "confirm"
        assert _intent("yep") == "confirm"
        assert _intent("correct") == "confirm"
        assert _intent("that's right") == "confirm"
        assert _intent("sounds good") == "confirm"
        assert _intent("book it") == "confirm"

    def test_deny(self):
        assert _intent("no") == "deny"
        assert _intent("nope") == "deny"
        assert _intent("that's wrong") == "deny"
        assert _intent("incorrect") == "deny"

    def test_change_value(self):
        assert _intent("actually change the time to 8pm") == "change_value"
        assert _intent("wait, make it 8 instead") == "change_value"
        assert _intent("switch to friday") == "change_value"


class TestSlotIntents:
    def test_provide_date(self):
        assert _intent("tomorrow") == "provide_date"
        assert _intent("friday") == "provide_date"
        assert _intent("January 5") == "provide_date"

    def test_provide_time(self):
        assert _intent("7pm") == "provide_time"
        assert _intent("7:30") == "provide_time"
        assert _intent("noon") == "provide_time"

    def test_provide_party_size(self):
        assert _intent("for 4") == "provide_party_size"
        assert _intent("party of 6") == "provide_party_size"
        assert _intent("just me") == "provide_party_size"

    def test_provide_name(self):
        assert _intent("my name is John") == "provide_name"
        assert _intent("this is Sarah") == "provide_name"

    def test_provide_phone(self):
        assert _intent("555-123-4567") == "provide_phone"
        assert _intent("my number is 555-123-4567") == "provide_phone"


class TestMetaQuestions:
    def test_ask_hours(self):
        assert _intent("what time do you open") == "ask_hours"
        assert _intent("what are your hours") == "ask_hours"
        assert _intent("how late are you open") == "ask_hours"

    def test_ask_location(self):
        assert _intent("where are you") == "ask_location"
        assert _intent("what's your address") == "ask_location"

    def test_ask_menu(self):
        assert _intent("do you have vegetarian options") == "ask_menu"
        assert _intent("what's on your menu") == "ask_menu"

    def test_ask_parking(self):
        assert _intent("do you have parking") == "ask_parking"
        assert _intent("where can I park") == "ask_parking"

    def test_repeat(self):
        assert _intent("can you repeat that") == "repeat"
        assert _intent("say that again") == "repeat"
        assert _intent("pardon?") == "repeat"


class TestFallback:
    def test_unknown_returns_fallback(self):
        # Words that don't match any rule
        assert _intent("xyzzy frobnicate") == "fallback"

    def test_empty_returns_silence(self):
        assert _intent("") == "silence"
        assert _intent("   ") == "silence"

    def test_returns_ranked_list(self):
        intents = classify("tomorrow at 7pm for 4 people")
        assert len(intents) >= 2
        # All confidences should be > 0 since they all matched something
        assert all(i.confidence > 0 for i in intents)
        # Should be sorted desc
        confs = [i.confidence for i in intents]
        assert confs == sorted(confs, reverse=True)
