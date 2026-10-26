"""Whole phone calls, replayed through Assistant. These are the acceptance tests for the policy.

Clock is frozen at Monday 2026-10-26 10:00 (see conftest.py).
"""
from datetime import datetime

from app.brain.state import State


def say(bot, *lines):
    """Say several sentences; return the last TurnResult."""
    result = None
    for line in lines:
        result = bot.hear(line)
    return result


def test_perfect_call_books_the_appointment(call, calendar):
    r = say(call, "hi, I need a cleaning tomorrow at 2 pm")
    assert r.state is State.ASK_PATIENT
    r = say(call, "Sara Khan")
    assert r.state is State.ASK_PHONE
    r = say(call, "03123456789")
    assert r.state is State.CONFIRM
    assert "cleaning" in r.reply and "Sara Khan" in r.reply and "2:00 PM" in r.reply
    r = say(call, "yes that is correct")
    assert r.done and "booked" in r.actions
    assert calendar.is_taken(datetime(2026, 10, 27, 14, 0))


def test_service_then_time_in_separate_turns(call):
    assert say(call, "I want to book an appointment").state is State.ASK_SERVICE
    assert say(call, "a checkup").state is State.ASK_WHEN
    assert say(call, "friday").state is State.ASK_WHEN          # date but no time yet
    r = say(call, "11")                                          # bare number = time, we asked
    assert r.state is State.ASK_PATIENT


def test_taken_slot_offers_alternatives_and_second_one_is_picked(call, calendar):
    calendar.book(datetime(2026, 10, 27, 9, 0), "Other", "03001112222", "checkup")
    r = say(call, "wisdom tooth extraction tomorrow at 9 am")
    assert r.state is State.OFFER_ALTERNATIVE
    assert "slot_taken" in r.actions and "offer_alternatives" in r.actions
    r = say(call, "the second one")
    assert r.state is State.ASK_PATIENT
    assert call.session.appt_time.strftime("%H:%M") == "10:00"


def test_yes_to_offer_takes_the_first_slot(call, calendar):
    calendar.book(datetime(2026, 10, 27, 9, 0), "Other", "03001112222", "checkup")
    say(call, "cleaning tomorrow at 9 am")
    say(call, "yes please")
    assert call.session.appt_time.strftime("%H:%M") == "09:30"


def test_caller_can_name_a_new_time_instead_of_picking(call, calendar):
    calendar.book(datetime(2026, 10, 27, 9, 0), "Other", "03001112222", "checkup")
    say(call, "cleaning tomorrow at 9 am")
    r = say(call, "no, how about 3 pm")
    assert r.state is State.ASK_PATIENT
    assert call.session.appt_time.strftime("%H:%M") == "15:00"


def test_correction_at_confirm_beats_yes(call):
    say(call, "checkup tomorrow at 11 am", "Bob", "03123456789")
    r = say(call, "yes but make it 1 pm")
    assert r.state is State.CONFIRM and "1:00 PM" in r.reply
    assert not call.session.booking_ref
    assert say(call, "yes").done


def test_no_at_confirm_asks_what_to_change(call):
    say(call, "checkup tomorrow at 11 am", "Bob", "03123456789")
    r = say(call, "no")
    assert "ask_what_to_change" in r.actions and r.state is State.CONFIRM
    r = say(call, "change the time to 4 pm")
    assert r.state is State.CONFIRM and "4:00 PM" in r.reply


def test_new_patient_relation_clears_the_old_name(call):
    say(call, "extraction for my mother tomorrow at 11 am", "Alice")
    assert call.session.name == "Alice"
    r = say(call, "03123456789")
    assert r.state is State.CONFIRM
    r = say(call, "sorry it is for my father")
    assert r.state is State.ASK_PATIENT and call.session.name is None
    r = say(call, "Bob")
    assert r.state is State.CONFIRM and "Bob" in r.reply


def test_price_question_is_answered_then_the_pending_question_is_repeated(call):
    say(call, "I need a root canal")
    r = say(call, "how much is it")
    assert "12000" in r.reply and r.state is State.ASK_WHEN
    assert r.reply.endswith("What day and time would you like to come in?")


def test_discount_is_refused_never_agreed(call):
    say(call, "I need a root canal")
    r1 = say(call, "can you make it 8k")
    r2 = say(call, "please give a discount")
    assert r1.actions[0] == "discount_refusal_1" and r2.actions[0] == "discount_refusal_2"
    assert "8" not in r1.reply and call.session.appt_time is None
    assert r1.state is State.ASK_WHEN


def test_hours_question_uses_real_opening_hours(call):
    r = say(call, "what are your clinic timings")
    assert "Monday to Saturday" in r.reply and "closed on Sunday" in r.reply
    assert r.state is State.ASK_SERVICE


def test_sunday_is_refused_and_next_open_slots_offered(call):
    r = say(call, "cleaning on sunday at 11")
    assert "closed_day" in r.actions and r.state is State.OFFER_ALTERNATIVE
    assert call.session.offered_slots[0] == datetime(2026, 11, 2, 9, 0)


def test_outside_hours_is_refused(call):
    r = say(call, "checkup tomorrow at 7 am")
    assert "outside_hours" in r.actions and r.state is State.OFFER_ALTERNATIVE


def test_time_in_the_past_is_refused(call):
    r = say(call, "checkup today at 9 am")
    assert "time_in_past" in r.actions and r.state is State.ASK_WHEN
    assert call.session.appt_time is None


def test_urgent_caller_gets_the_earliest_slots(call):
    r = say(call, "I have a severe toothache")
    assert "urgent_ack" in r.actions and "earliest_available" in r.actions
    assert r.state is State.OFFER_ALTERNATIVE
    assert call.session.offered_slots[0] == datetime(2026, 10, 26, 10, 30)  # 30 min lead


def test_cancel_is_detected_but_unsupported(call):
    r = say(call, "I want to cancel my appointment")
    assert "cancel_unsupported" in r.actions and not r.done


def test_garbled_three_times_hands_off(call):
    assert say(call, "qwerty").actions[0] == "not_understood_1"
    assert say(call, "asdfgh").actions[0] == "not_understood_2"
    r = say(call, "zxcvbn")
    assert r.done and "handoff" in r.actions


def test_understood_turn_resets_the_failure_count(call):
    say(call, "qwerty", "asdfgh")
    say(call, "a cleaning")
    assert call.session.fail_count == 0


def test_bad_phone_is_reasked(call):
    say(call, "checkup tomorrow at 11 am", "Bob")
    r = say(call, "12345")
    assert r.state is State.ASK_PHONE and "bad_phone" in r.actions


def test_goodbye_midway_books_nothing(call, calendar):
    say(call, "checkup tomorrow at 11 am")
    r = say(call, "never mind, bye")
    assert r.done and "goodbye_no_booking" in r.actions
    assert calendar.booked_slots == {}


def test_human_request_hands_off(call):
    r = say(call, "let me talk to a human")
    assert r.done and "human_handoff" in r.actions


def test_repeat_says_the_last_reply_again(call):
    first = say(call, "a cleaning")
    again = say(call, "sorry can you repeat that")
    assert again.reply == first.reply


def test_after_the_call_ends_nothing_changes(call):
    say(call, "bye")
    r = say(call, "book a cleaning")
    assert "already_done" in r.actions
