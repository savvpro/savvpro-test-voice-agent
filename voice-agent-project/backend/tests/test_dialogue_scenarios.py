"""Scripted phone calls. Each test is one 'messy caller' behaviour from DESIGN.md."""

from __future__ import annotations

import datetime as dt

from conftest import FRIDAY, GOOD_PHONE, GOOD_PHONE_DIGITS, TOMORROW, Call


def hhmm(slot: dt.datetime) -> str:
    return f"{slot:%H:%M}"


# ------------------------------------------------------------------ happy paths
def test_greeting_offers_the_three_jobs(call):
    assert "book, reschedule, or cancel" in call.greeting
    assert call.state == "ask_intent"


def test_booking_one_slot_per_turn(call):
    slot = call.free_slots("dental", TOMORROW)[0]
    call.say("I'd like to book an appointment")
    assert call.say("dental").startswith("Which day")
    assert "What time" in call.say("tomorrow")
    assert "full name" in call.say(hhmm(slot))
    assert "mobile number" in call.say("my name is Zainab Noor")
    reply = call.say(GOOD_PHONE)
    assert call.state == "confirming" and "Zainab Noor" in reply and "Dr. Ahmed" in reply
    assert "0 3 2 1" in reply  # the number is read back digit by digit
    done = call.say("yes")
    assert "confirmation number" in done and call.state == "ask_more"
    booked = call.scheduler.find_by_phone(GOOD_PHONE_DIGITS)
    assert len(booked) == 1 and booked[0].start == slot and booked[0].name == "Zainab Noor"


def test_everything_in_one_sentence_goes_straight_to_name(call):
    slot = call.free_slots("skin", TOMORROW)[0]
    reply = call.say(f"book a skin appointment tomorrow at {hhmm(slot)}")
    assert "full name" in reply and call.session.slots.specialty == "skin"


def test_after_booking_caller_can_book_another_or_hang_up(call):
    slot = call.free_slots("general", TOMORROW)[0]
    call.say(f"book general tomorrow {hhmm(slot)}")
    call.say("Ayesha Noor")
    call.say(GOOD_PHONE)
    call.say("yes")
    assert "Which doctor" in call.say("yes, book another one") or call.state == "collecting"
    call2 = Call()
    slot = call2.free_slots("general", TOMORROW)[0]
    call2.say(f"book general tomorrow {hhmm(slot)}")
    call2.say("Ayesha Noor")
    call2.say(GOOD_PHONE)
    call2.say("yes")
    assert "Goodbye" in call2.say("no thanks") and call2.state == "ended"


# ------------------------------------------------------------- caller changes mind
def test_caller_changes_the_time_halfway(call):
    free = call.free_slots("general", TOMORROW)
    call.say(f"book general tomorrow at {hhmm(free[0])}")
    reply = call.say(f"actually make it {hhmm(free[1])}")
    assert call.session.slots.at == free[1].time()
    assert reply.startswith("Okay,")  # the change is acknowledged out loud


def test_caller_changes_the_day_at_confirmation(call):
    free = call.free_slots("general", TOMORROW)[0]
    call.say(f"book general tomorrow {hhmm(free)}")
    call.say("Sara Ali")
    call.say(GOOD_PHONE)
    assert call.state == "confirming"
    target = FRIDAY
    same_time = [s for s in call.free_slots("general", target) if s.time() == free.time()]
    reply = call.say("no, make it friday")
    assert call.session.slots.day == target
    if same_time:
        assert call.state == "confirming" and "Friday" in reply
    else:
        assert call.state == "offering"  # that time is taken on Friday: alternatives offered


def test_correction_with_not(call):
    call.say("book dental")
    call.say("tomorrow")
    call.say("11 am")
    call.say("Sara Ali")
    call.say(GOOD_PHONE)
    call.say("no, I said 10 am not 11 am")
    assert call.session.slots.at == dt.time(10, 0)


def test_no_at_confirmation_asks_what_to_change(call):
    slot = call.free_slots("general", TOMORROW)[0]
    call.say(f"book general tomorrow {hhmm(slot)}")
    call.say("Sara Ali")
    call.say(GOOD_PHONE)
    reply = call.say("no")
    assert "What would you like to change" in reply and call.session.pending == "change"
    reply = call.say("the day")
    assert call.session.slots.day is None and "Which day" in reply


def test_switching_from_booking_to_reschedule(call):
    call.say("book a dental appointment")
    reply = call.say("actually I want to reschedule my appointment")
    assert call.session.intent.value == "reschedule" and "phone number" in reply


def test_cancel_during_booking_drops_the_booking(call):
    call.say("book dental tomorrow")
    reply = call.say("cancel")
    assert "dropped" in reply and call.state == "ask_more"
    assert call.scheduler.find_by_phone(GOOD_PHONE_DIGITS) == []


def test_never_mind_drops_the_flow(call):
    call.say("book dental")
    assert "dropped" in call.say("never mind")


def test_start_over_clears_everything(call):
    call.say("book dental tomorrow")
    reply = call.say("let's start over")
    assert "start over" in reply and call.session.slots.specialty is None and call.state == "ask_intent"


# ------------------------------------------------------------ availability problems
def test_taken_slot_offers_alternatives_and_caller_picks_second(call):
    busy = call.busy_slot("general", FRIDAY)
    reply = call.say(f"book general friday at {hhmm(busy)}")
    assert call.state == "offering" and "isn't available" in reply and len(call.session.offers) == 3
    second = call.session.offers[1]
    call.say("the second one")
    assert call.session.slots.at == second.time() and call.session.slots.day == second.date()
    assert "full name" in call.last.reply


def test_caller_picks_an_offer_by_saying_its_time(call):
    busy = call.busy_slot("general", FRIDAY)
    call.say(f"book general friday {hhmm(busy)}")
    pick = call.session.offers[0]
    call.say(hhmm(pick) if pick.date() == FRIDAY else "the first one")
    assert call.session.slots.at == pick.time()


def test_none_of_those_asks_for_another_time(call):
    busy = call.busy_slot("general", FRIDAY)
    call.say(f"book general friday {hhmm(busy)}")
    reply = call.say("no, none of those")
    assert "other day or time" in reply and call.state == "collecting"


def test_yes_to_several_offers_asks_which(call):
    busy = call.busy_slot("general", FRIDAY)
    call.say(f"book general friday {hhmm(busy)}")
    assert "first, second, or third" in call.say("yes")


def test_caller_ignores_offers_and_names_a_new_time(call):
    busy = call.busy_slot("general", FRIDAY)
    call.say(f"book general friday {hhmm(busy)}")
    other = [s for s in call.free_slots("general", TOMORROW)][0]
    call.say(f"how about tomorrow at {hhmm(other)}")
    assert call.session.slots.day == TOMORROW and call.state == "collecting"
    assert "full name" in call.last.reply


def test_morning_request_offers_morning_slots(call):
    reply = call.say("book dental tomorrow morning")
    morning = [s for s in call.free_slots("dental", TOMORROW) if s.hour < 12]
    if morning:
        assert call.state == "offering" and "For the morning" in reply
        assert all(o.hour < 12 for o in call.session.offers)
    else:
        assert "don't have any morning" in reply


def test_vague_week_asks_for_a_specific_day(call):
    call.say("book dental")
    reply = call.say("sometime next week")
    assert "Which day" in reply and "Monday to Saturday" in reply


def test_closed_sunday_is_explained(call):
    call.say("book dental")
    reply = call.say("sunday")
    assert "closed on Sundays" in reply and call.session.slots.day is None
    assert call.session.pending == "day"


def test_past_date_is_rejected(call):
    call.say("book dental")
    reply = call.say("1 november")
    assert "already passed" in reply


def test_too_far_ahead_is_rejected(call):
    call.say("book dental")
    assert "thirty days" in call.say("15 january")


def test_out_of_hours_time_is_rejected(call):
    call.say("book dental tomorrow")
    reply = call.say("7 pm")
    assert "nine AM to four thirty PM" in reply and call.session.slots.at is None


def test_time_earlier_today_is_rejected():
    afternoon = Call(now=dt.datetime(2026, 11, 2, 14, 0))
    afternoon.say("book general today")
    assert "already passed" in afternoon.say("10 am")


def test_off_grid_time_gets_nearby_options(call):
    day_free = call.free_slots("general", TOMORROW)
    call.say("book general tomorrow")
    reply = call.say("10:15 am")
    assert "hour or half hour" in reply and call.state == "offering"
    assert day_free  # sanity: the fake schedule is not empty


def test_slot_lost_between_confirmation_and_booking(call):
    slot = call.free_slots("general", TOMORROW)[0]
    call.say(f"book general tomorrow {hhmm(slot)}")
    call.say("Sara Ali")
    call.say(GOOD_PHONE)
    call.scheduler.book("Someone Else", "03331234567", "general", slot)  # another caller wins the race
    reply = call.say("yes")
    assert "just taken" in reply and call.state in ("offering", "collecting")
    assert call.scheduler.find_by_phone(GOOD_PHONE_DIGITS) == []


def test_duplicate_booking_same_day_is_blocked(call):
    free = call.free_slots("general", TOMORROW)
    call.scheduler.book("Sara Ali", GOOD_PHONE_DIGITS, "general", free[0])
    call.say(f"book general tomorrow {hhmm(free[1])}")
    call.say("Sara Ali")
    reply = call.say(GOOD_PHONE)
    assert "already have an appointment" in reply and "reschedule" in reply
    assert len(call.scheduler.find_by_phone(GOOD_PHONE_DIGITS)) == 1


# ------------------------------------------------------------- bad input handling
def test_invalid_phone_is_reprompted(call):
    slot = call.free_slots("general", TOMORROW)[0]
    call.say(f"book general tomorrow {hhmm(slot)}")
    call.say("Sara Ali")
    reply = call.say("zero three two one one two three four five six seven eight")  # 12 digits
    assert "full eleven digit" in reply and call.session.slots.phone is None
    assert call.state == "collecting"
    assert "Let me confirm" in call.say(GOOD_PHONE)


def test_silence_then_handoff_after_three_failures(call):
    first = call.say("")
    assert first.startswith("I didn't hear anything") and call.state == "ask_intent"
    second = call.say("")
    assert second.startswith("Let me try again") and "book an appointment" in second
    third = call.say("")
    assert "receptionist" in third and call.state == "handoff" and call.last.ended


def test_gibberish_counts_as_failure_but_progress_resets_the_counter(call):
    call.say("blargh")
    assert call.session.fails == 1
    call.say("book dental")
    assert call.session.fails == 0


def test_low_stt_confidence_is_treated_as_not_heard(call):
    reply = call.say("book a dental appointment", confidence=0.2)
    assert reply.startswith("I'm not sure I caught that") and call.session.intent is None


def test_repeat_returns_last_reply(call):
    call.say("book dental")
    last = call.session.last_reply
    assert call.say("sorry, can you repeat that?") == last


def test_faq_mid_flow_answers_then_returns_to_the_question(call):
    call.say("book dental")
    reply = call.say("what time do you open?")
    assert "Monday to Saturday" in reply and "Which day" in reply
    assert call.state == "collecting"


def test_location_faq(call):
    assert "12 Main Boulevard" in call.say("where are you located?")


def test_human_request_hands_off(call):
    call.say("book dental")
    reply = call.say("I want to speak to a real person")
    assert "receptionist" in reply and call.state == "handoff"


def test_goodbye_mid_booking_changes_nothing(call):
    call.say("book dental tomorrow")
    reply = call.say("bye")
    assert "haven't made any changes" in reply and call.state == "ended"


def test_turns_after_the_call_ended_are_harmless(call):
    call.say("bye")
    assert "ended" in call.say("hello?")


def test_slot_without_intent_word_assumes_booking(call):
    call.say("dentist tomorrow please")
    assert call.session.intent.value == "book" and call.session.slots.specialty == "dental"


# ---------------------------------------------------------- reschedule and cancel
def test_reschedule_happy_path(call):
    old = call.scheduler.find_by_phone("03001234567")[0]
    call.say("I need to reschedule my appointment")
    reply = call.say("zero three zero zero one two three four five six seven")
    assert "Sara Malik" in reply and "Let's find a new time" in reply and "Which day" in reply
    target = next(s for s in call.free_slots("general", FRIDAY))
    call.say("friday")
    reply = call.say(hhmm(target))
    assert call.state == "confirming" and "I'll move your appointment" in reply
    assert "confirmation number" not in reply
    call.say("yes")
    assert call.scheduler.find_by_phone("03001234567")[0].start == target
    assert call.scheduler.find_by_phone("03001234567")[0].id == old.id


def test_reschedule_to_the_same_slot_is_refused(call):
    old = call.scheduler.find_by_phone("03001234567")[0]
    call.say("reschedule")
    call.say("03001234567")
    reply = call.say(f"{old.start:%A} at {hhmm(old.start)}")
    assert "already the time of your appointment" in reply


def test_lookup_not_found_twice_hands_off(call):
    call.say("cancel my appointment")
    first = call.say("03451112223")
    assert "couldn't find" in first and call.state == "collecting"
    second = call.say("03451112224")
    assert "receptionist" in second and call.state == "handoff"


def test_cancel_happy_path(call):
    call.say("I want to cancel my appointment")
    reply = call.say("03111234567")
    assert call.state == "confirming" and reply.startswith("Thank you, Ali Raza.") and "dental" in reply
    assert reply.count("dental appointment") == 1  # details are read out once, not twice
    assert "on tomorrow" not in reply
    done = call.say("yes")
    assert "cancelled" in done and call.scheduler.find_by_phone("03111234567") == []


def test_cancel_declined_keeps_the_appointment(call):
    call.say("cancel my appointment")
    call.say("03111234567")
    reply = call.say("no")
    assert "left your appointment as it is" in reply
    assert len(call.scheduler.find_by_phone("03111234567")) == 1


def test_cancel_with_the_number_in_the_first_sentence(call):
    reply = call.say("cancel my appointment, my number is 03001234567")
    assert call.state == "confirming" and "cancel your general appointment" in reply


# --------------------------------------------------------------------- trace / UI
def test_every_turn_exposes_a_rule_and_state_change(call):
    call.say("book dental")
    assert call.last.trace.rule == "advance.ask_day"
    assert call.last.trace.state_before == "ask_intent" and call.last.trace.state_after == "collecting"
    assert "intent:book" in call.last.trace.intents
    assert call.last.trace.entities["specialty"] == "dental"


# ------------------------------------------------- fixes found by trying it with a real microphone
def _ready_for_phone(call):
    slot = call.free_slots("general", TOMORROW)[0]
    call.say(f"book general tomorrow {hhmm(slot)}")
    call.say("Sara Ali")


def test_phone_number_split_across_two_utterances_is_joined(call):
    _ready_for_phone(call)
    reply = call.say("0333")
    assert "I have 0 3 3 3 so far" in reply and call.session.slots.phone is None
    assert "Let me confirm" in call.say("7403766")
    assert call.session.slots.phone == "03337403766"


def test_restating_the_whole_number_after_a_partial_works(call):
    _ready_for_phone(call)
    call.say("033740")
    assert "Let me confirm" in call.say("03337403766")


def test_silence_after_a_bad_number_repeats_the_plain_question(call):
    _ready_for_phone(call)
    call.say("zero three two one one two three four five six seven eight")
    assert call.say("") == "I didn't hear anything. What's your mobile number? Please say all eleven digits."


def test_silence_at_the_read_back_does_not_repeat_the_whole_summary(call):
    _ready_for_phone(call)
    call.say(GOOD_PHONE)
    first = call.say("")
    assert first == "I didn't hear anything. Please say yes to confirm, or no to change something."
    second = call.say("")
    assert second.startswith("Let me try again. Let me confirm")  # the full summary once, on the second try
    assert call.say("yes").startswith("You're all set")  # a late answer still works


def test_out_of_hours_reply_is_short(call):
    call.say("book dental tomorrow")
    assert call.say("7 pm") == "Appointments run from nine AM to four thirty PM. What time works for you?"
