"""
Unit tests — Intent classification (brain/intents.py)

Run:  cd backend && pytest tests/test_intents.py -v
"""

import pytest
from brain.intents import classify, Intent


class TestBookAppointment:
    def test_standard(self):
        assert classify("I'd like to book an appointment") == Intent.BOOK_APPOINTMENT

    def test_schedule(self):
        assert classify("Can I schedule a visit?") == Intent.BOOK_APPOINTMENT

    def test_need_to_see(self):
        assert classify("I need to see a doctor") == Intent.BOOK_APPOINTMENT


class TestReschedule:
    def test_reschedule_word(self):
        assert classify("I need to reschedule") == Intent.RESCHEDULE

    def test_move_appointment(self):
        assert classify("Can I move my appointment?") == Intent.RESCHEDULE


class TestCancel:
    def test_cancel_appointment(self):
        assert classify("I want to cancel my appointment") == Intent.CANCEL

    def test_cancel_standalone(self):
        assert classify("cancel") == Intent.CANCEL


class TestConfirm:
    @pytest.mark.parametrize("utterance", [
        "yes", "Yes", "yep", "yeah", "correct", "right",
        "that's right", "sounds good", "perfect", "okay", "ok",
        "sure", "absolutely", "great",
    ])
    def test_confirm_variants(self, utterance):
        assert classify(utterance) == Intent.CONFIRM


class TestDeny:
    @pytest.mark.parametrize("utterance", [
        "no", "nope", "nah", "wrong", "incorrect",
        "that's wrong", "not right", "not quite",
    ])
    def test_deny_variants(self, utterance):
        assert classify(utterance) == Intent.DENY


class TestGoodbye:
    @pytest.mark.parametrize("utterance", [
        "bye", "goodbye", "thank you", "that's all", "see you",
    ])
    def test_goodbye_variants(self, utterance):
        assert classify(utterance) == Intent.GOODBYE


class TestRepeat:
    def test_pardon(self):
        assert classify("pardon?") == Intent.REPEAT

    def test_say_again(self):
        assert classify("could you say that again?") == Intent.REPEAT

    def test_didnt_catch(self):
        assert classify("I didn't catch that") == Intent.REPEAT


class TestCorrectionIntents:
    """
    Critical: correction intents must be detected even when mixed with slot data.
    """

    def test_change_date_actually(self):
        assert classify("actually make it Tuesday") == Intent.CHANGE_DATE

    def test_change_date_instead(self):
        assert classify("Wednesday instead") == Intent.CHANGE_DATE

    def test_change_time_actually(self):
        assert classify("actually I'd prefer 3pm") == Intent.CHANGE_TIME

    def test_change_time_earlier(self):
        assert classify("can we do an earlier time?") == Intent.CHANGE_TIME

    def test_change_doctor_actually(self):
        assert classify("actually I'd prefer Dr. Khan") == Intent.CHANGE_DOCTOR

    def test_change_doctor_different(self):
        assert classify("I'd like a different doctor") == Intent.CHANGE_DOCTOR

    def test_change_name_sorry(self):
        assert classify("sorry, I said the wrong name") == Intent.CHANGE_NAME

    def test_change_name_actually(self):
        assert classify("my name is actually Sara") == Intent.CHANGE_NAME

    def test_correction_beats_provide_info(self):
        """'actually Tuesday' must NOT fall through to provide_info."""
        intent = classify("actually Tuesday")
        assert intent == Intent.CHANGE_DATE
        assert intent != Intent.PROVIDE_INFO


class TestProvideInfo:
    def test_plain_name(self):
        assert classify("John Smith") == Intent.PROVIDE_INFO

    def test_date_without_correction_word(self):
        assert classify("Tuesday") == Intent.PROVIDE_INFO

    def test_time_without_correction_word(self):
        assert classify("3pm") == Intent.PROVIDE_INFO

