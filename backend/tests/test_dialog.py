"""Whole calls, turn by turn, including the messy ones."""

from datetime import datetime

from tests.conftest import talk


def test_happy_path_booking(call, calendar):
    d = talk(call, "hi I'd like to book a cleaning", "next tuesday at 3", "my name is Jane Doe", "555 123 4567")
    assert d.action == "confirm"
    assert "Jane Doe" in d.reply and "3 PM" in d.reply
    d = talk(call, "yes please")
    assert d.action == "booked" and d.ended
    booking = calendar.find_by_phone("5551234567")
    assert booking.start == datetime(2026, 11, 3, 15, 0)
    assert booking.service == "cleaning"


def test_everything_in_one_sentence(call):
    d = talk(call, "book a checkup tomorrow at 10 am, my name is Sam Rivera, number 555 222 3333")
    assert d.action == "confirm"


def test_caller_changes_time_halfway(call, calendar):
    talk(call, "I need a checkup tomorrow at 10 am")
    d = talk(call, "actually make it 2 pm")
    assert any("changed time" in r for r in d.reasons)
    talk(call, "Sam Rivera", "five five five two two two three three three three", "yes")
    assert calendar.find_by_phone("5552223333").start == datetime(2026, 10, 27, 14, 0)


def test_make_it_four_changes_the_time(call):
    talk(call, "I'd like a cleaning next Tuesday at 3")
    d = talk(call, "Actually, make it 4")
    assert call.s.at.hour == 16
    assert any("changed time: 3 PM -> 4 PM" in r for r in d.reasons)


def test_correction_at_confirmation(call, calendar):
    talk(call, "book a whitening thursday at 9", "Pat Lee", "5553334444")
    d = talk(call, "no wait, make it friday")
    assert d.action == "confirm" and "Friday" in d.reply
    talk(call, "yes")
    assert calendar.find_by_phone("5553334444").start == datetime(2026, 10, 30, 9, 0)


def test_plain_no_at_confirmation_asks_what_to_change(call):
    talk(call, "book a filling thursday at 9", "Pat Lee", "5553334444")
    d = talk(call, "no")
    assert d.action == "ask_change"
    d = talk(call, "2 pm")
    assert d.action == "confirm" and "2 PM" in d.reply


def _demo_slot_request(call) -> str:
    taken = call.cal.bookings["BS-1001"].start  # the demo booking
    return f"book a cleaning on {taken.strftime('%B').lower()} {taken.day} at 10 am"


def test_taken_slot_offers_alternatives_and_accepts_choice(call):
    d = talk(call, _demo_slot_request(call))
    assert d.action == "offer_alternatives" and "taken" in d.reply
    assert "October" in d.reply and "AM is already taken" in d.reply  # month and AM/PM keep their capitals
    offers = call.s.offers
    d = talk(call, "the second one")
    assert call.s.at == offers[1].time()
    assert d.action == "ask_name"


def test_reject_offers_then_pick_new_time(call):
    talk(call, _demo_slot_request(call))
    d = talk(call, "no")
    assert d.action == "ask_time"


def test_closed_day_and_outside_hours(call):
    d = talk(call, "book a filling on sunday")
    assert d.action == "invalid_date" and "closed on Sundays" in d.reply
    d = talk(call, "saturday at 4")
    assert d.action == "offer_alternatives" and "not open" in d.reply


def test_far_date_and_past_time_rejected(call):
    d = talk(call, "book a cleaning on october 1st")  # already past: rolls to next year, too far ahead
    assert d.action == "invalid_date"
    d = talk(call, "today at 9 am")  # earlier today
    assert d.action == "invalid_time"


def test_ambiguous_hour_read_as_afternoon(call):
    d = talk(call, "cleaning tomorrow at 2")
    assert call.s.at.hour == 14
    assert any("without AM/PM" in r for r in d.reasons)


def test_part_of_day_offers_slots(call):
    d = talk(call, "a cleaning tomorrow afternoon")
    assert d.action == "offer_alternatives"
    assert all(o.hour >= 12 for o in call.s.offers)


def test_reschedule_existing_booking(call, calendar):
    d = talk(call, "can I reschedule my appointment", "555 014 2233")
    assert d.state["name"] == "Jordan Lee" and d.action == "ask_date"
    talk(call, "friday", "11 am")
    d = talk(call, "yes")
    assert d.action == "moved"
    assert calendar.bookings["BS-1001"].start == datetime(2026, 10, 30, 11, 0)


def test_cancel_existing_booking(call, calendar):
    d = talk(call, "cancel my appointment", "5550142233")
    assert d.action == "confirm_cancel"
    d = talk(call, "yes")
    assert d.action == "cancelled" and "BS-1001" not in calendar.bookings


def test_unknown_phone_for_cancel(call):
    d = talk(call, "cancel my appointment", "555 999 0000")
    assert d.action == "booking_not_found"


def test_switch_from_booking_to_cancel(call):
    talk(call, "I want to book a cleaning")
    d = talk(call, "actually I want to cancel my appointment")
    assert call.s.task == "cancel" and d.action == "ask_lookup"


def test_emergency_gets_earliest_slot(call):
    d = talk(call, "I have a really bad toothache")
    assert d.action == "offer_urgent" and "911" in d.reply
    d = talk(call, "the first one")
    assert call.s.service == "emergency" and d.action == "ask_name"


def test_faq_mid_booking_returns_to_question(call):
    talk(call, "book a cleaning tomorrow at 10 am")
    d = talk(call, "where are you located")
    assert d.action == "answer_location"
    assert d.reply.endswith("What's your full name?")
    assert call.s.service == "cleaning"  # nothing lost


def test_repeat_and_restart(call):
    first = talk(call, "book a cleaning")
    d = talk(call, "sorry, say that again")
    assert d.reply == first.reply
    d = talk(call, "let's start over")
    assert d.action == "restart" and call.s.service is None


def test_three_misses_transfer_to_front_desk(call):
    talk(call, "book a cleaning tomorrow at 10 am")
    talk(call, "no", "blah")
    d = talk(call, "hmm what")
    assert d.action == "transfer" and d.ended


def test_ask_for_a_person(call):
    d = talk(call, "can I speak to a real person")
    assert d.action == "transfer" and d.ended


def test_silence(call):
    d = talk(call, "")
    assert d.action == "no_input"


def test_name_not_taken_from_filler(call):
    talk(call, "book a cleaning tomorrow at 10 am")
    talk(call, "the first")
    assert call.s.name is None


def test_after_end_nothing_happens(call):
    talk(call, "bye")
    d = talk(call, "book a cleaning")
    assert d.action == "ended"


def test_slot_taken_by_another_caller_before_confirm(call, calendar):
    talk(call, "book a cleaning tomorrow at 10 am", "Pat Lee", "5553334444")
    calendar.add("Other Caller", "5557778888", "cleaning", datetime(2026, 10, 27, 10, 0))
    d = talk(call, "yes")
    assert d.action == "offer_alternatives" and "just taken" in d.reply


def test_every_turn_explains_itself(call):
    d = talk(call, "book a cleaning next tuesday at 3")
    assert d.intent == "book" and d.confidence > 0
    assert d.extracted["service"] == "cleaning"
    assert d.reasons


# --- phone numbers are optional and accepted in any format ---------------


def test_book_without_a_phone_number(call, calendar):
    d = talk(call, "book a cleaning tomorrow at 10 am", "Jane Doe")
    assert d.action == "ask_phone" and "optional" in d.reply
    d = talk(call, "skip")
    assert d.action == "confirm" and "text" not in d.reply
    assert any("optional" in r for r in d.reasons)
    d = talk(call, "yes")
    assert d.action == "booked"
    assert next(b for b in calendar.bookings.values() if b.name == "Jane Doe").phone == ""


def test_no_thanks_at_phone_prompt_does_not_hang_up(call):
    d = talk(call, "book a cleaning tomorrow at 10 am", "Jane Doe", "no thanks")
    assert d.action == "confirm" and not d.ended


def test_phone_number_in_any_format(call, calendar):
    d = talk(call, "book a cleaning tomorrow at 10 am", "Jane Doe", "it's 135 567454 2132")
    assert d.action == "confirm" and "ending in 2132" in d.reply
    talk(call, "yes")
    assert calendar.find_by_phone("1355674542132").name == "Jane Doe"


def test_cancel_by_name(call, calendar):
    d = talk(call, "cancel my appointment", "Jordan Lee")
    assert d.action == "confirm_cancel"
    talk(call, "yes")
    assert "BS-1001" not in calendar.bookings


def test_reschedule_by_first_name_and_country_code(call):
    d = talk(call, "I need to reschedule", "this is jordan")
    assert d.action == "ask_date"
    call2 = type(call)(call.cal, call.now)
    call2.greet()
    d = talk(call2, "I need to reschedule", "1 555 014 2233")
    assert d.action == "ask_date"


def test_unknown_name_for_cancel(call):
    d = talk(call, "cancel my appointment", "Taylor Smith")
    assert d.action == "booking_not_found"
