from datetime import date, datetime, time, timedelta

import pytest

from app.brain import Brain, MAX_FAILURES
from app.scheduler import Schedule, seed_demo

NOW = datetime(2026, 10, 26, 10, 0)   # Monday 10:00


@pytest.fixture
def brain():
    schedule = Schedule()
    return Brain(schedule, clock=lambda: NOW)


def call(brain, *lines):
    s = brain.new_session("t")
    results = [brain.handle(s, line) for line in lines]
    return s, results


def free_day_and_slots(brain, start=date(2026, 10, 27)):
    d = start
    while True:
        slots = brain.schedule.free_slots(d, NOW)
        if len(slots) >= 3:
            return d, slots
        d += timedelta(days=1)


def busy_hour(brain, d):
    return next(h for h in brain.schedule.hours_for(d) if not brain.schedule.is_free(d, time(h)))


def test_happy_path_one_step_at_a_time(brain):
    d, slots = free_day_and_slots(brain)
    s, r = call(brain, "I'd like to book an appointment", "a cleaning",
                f"{d:%B} {d.day}", f"at {slots[0].hour}", "sara khan", "yes")
    assert "What would you like to come in for" in r[0].reply
    assert r[3].state == "collecting" and "name" in r[3].reply
    assert r[4].state == "confirming" and "Sara Khan" in r[4].reply
    assert "confirmation number" in r[5].reply and r[5].state == "done"
    assert len(brain.schedule.find_by_name("sara khan", NOW.date())) == 1


def test_everything_in_one_sentence(brain):
    d, slots = free_day_and_slots(brain)
    _, r = call(brain, f"hi my name is Alex Lee, I need a filling on {d:%B} {d.day} at {slots[0].hour}")
    assert r[0].state == "confirming" and "filling" in r[0].reply and "Alex Lee" in r[0].reply


def test_caller_changes_time_at_confirmation(brain):
    d, slots = free_day_and_slots(brain)
    s, r = call(brain, f"cleaning on {d:%B} {d.day} at {slots[0].hour}", "sara khan",
                f"actually make it at {slots[1].hour}", "yes")
    assert r[2].state == "confirming" and f"{slots[1].hour % 12 or 12}" in r[2].reply
    assert brain.schedule.find_by_name("sara", NOW.date())[0].time == slots[1]


def test_caller_says_no_then_changes_day(brain):
    d, slots = free_day_and_slots(brain)
    _, r = call(brain, f"cleaning on {d:%B} {d.day} at {slots[0].hour}", "sara khan", "no", "change the time")
    assert "What would you like to change" in r[2].reply
    assert "What time" in r[3].reply


def test_sunday_is_closed(brain):
    _, r = call(brain, "book a checkup on sunday")
    assert "closed on Sundays" in r[0].reply and r[0].state == "collecting"


def test_past_date_rejected(brain):
    _, r = call(brain, "book a checkup today at 9 am")
    assert "already passed" in r[0].reply


def test_far_future_rejected(brain):
    _, r = call(brain, "book a checkup on january 5")
    assert "two months" in r[0].reply


def test_taken_slot_offers_alternatives_and_second_is_chosen(brain):
    d, _ = free_day_and_slots(brain)
    h = busy_hour(brain, d)
    s, r = call(brain, f"cleaning on {d:%B} {d.day} at {h}")
    assert r[0].state == "offering" and "already taken" in r[0].reply and len(r[0].alternatives) >= 1
    r2 = brain.handle(s, "the second one" if len(r[0].alternatives) > 1 else "the first one")
    assert "name" in r2.reply and s.slots["time"] is not None


def test_outside_hours_mentions_opening_times(brain):
    d, _ = free_day_and_slots(brain)
    _, r = call(brain, f"cleaning on {d:%B} {d.day} at 8 pm")
    assert "nine to twelve" in r[0].reply and r[0].state == "offering"


def test_half_hour_is_off_grid(brain):
    d, _ = free_day_and_slots(brain)
    _, r = call(brain, f"cleaning on {d:%B} {d.day} at 3:30 pm")
    assert "on the hour" in r[0].reply


def test_period_offers_slots_in_that_period(brain):
    d, _ = free_day_and_slots(brain)
    _, r = call(brain, f"a checkup on {d:%B} {d.day} in the afternoon")
    assert r[0].state == "offering" and all("PM" in a for a in r[0].alternatives)


def test_picking_a_time_after_new_day_during_offer(brain):
    d, _ = free_day_and_slots(brain)
    h = busy_hour(brain, d)
    s, r = call(brain, f"cleaning on {d:%B} {d.day} at {h}")
    d2, slots2 = free_day_and_slots(brain, d + timedelta(days=1))
    r2 = brain.handle(s, f"how about {d2:%B} {d2.day} at {slots2[0].hour}")
    assert r2.state == "collecting" and "name" in r2.reply


def test_hours_question_keeps_the_flow(brain):
    s, r = call(brain, "book a cleaning", "what are your hours")
    assert "closed on Sundays" in r[1].reply and "What day" in r[1].reply
    assert s.intent == "book"


def test_cancel_flow(brain):
    appt = seed_demo(brain.schedule, NOW.date())
    s, r = call(brain, "I need to cancel my appointment", "sara khan", "yes")
    assert "I found your cleaning" in r[1].reply and r[1].state == "confirming"
    assert "cancelled" in r[2].reply
    assert brain.schedule.find_by_name("sara khan", NOW.date()) == []


def test_cancel_declined_keeps_appointment(brain):
    seed_demo(brain.schedule, NOW.date())
    _, r = call(brain, "cancel my appointment", "sara khan", "no")
    assert "kept your appointment" in r[2].reply
    assert len(brain.schedule.find_by_name("sara khan", NOW.date())) == 1


def test_unknown_name_three_times_hands_off(brain):
    _, r = call(brain, "cancel my appointment", "bob", "bob", "bob")
    assert r[-1].ended and "receptionist" in r[-1].reply


def test_reschedule_flow(brain):
    old = seed_demo(brain.schedule, NOW.date())
    d, slots = free_day_and_slots(brain, old.day + timedelta(days=1))
    s, r = call(brain, "I want to reschedule", "sara khan", f"{d:%B} {d.day}", f"at {slots[0].hour}", "yes")
    assert "I found your cleaning" in r[1].reply
    assert "move your cleaning" in r[3].reply
    assert "moved" in r[4].reply
    appts = brain.schedule.find_by_name("sara khan", NOW.date())
    assert len(appts) == 1 and appts[0].day == d


def test_gibberish_three_times_hands_off(brain):
    _, r = call(brain, "blah", "asdf", "qwerty")
    assert r[-1].ended and r[-1].state == "ended"
    assert "receptionist" in r[-1].reply


def test_failures_reset_after_success(brain):
    s, r = call(brain, "blah", "asdf", "book a cleaning", "blah", "asdf")
    assert not s.ended


def test_emergency_escalates_immediately(brain):
    s, r = call(brain, "my face is swollen and I'm bleeding")
    assert r[0].ended and "on-call dentist" in r[0].reply


def test_human_request(brain):
    s, r = call(brain, "let me talk to a real person")
    assert r[0].ended


def test_repeat_says_last_reply_again(brain):
    s, r = call(brain, "book a cleaning", "can you repeat that")
    assert r[1].reply == r[0].reply


def test_empty_input_is_not_a_crash(brain):
    s, r = call(brain, "   ")
    assert "didn't catch" in r[0].reply


def test_second_booking_in_same_call(brain):
    d, slots = free_day_and_slots(brain)
    s, r = call(brain, f"cleaning on {d:%B} {d.day} at {slots[0].hour}", "sara khan", "yes",
                "yes", f"a checkup on {d:%B} {d.day} at {slots[1].hour}", "yes")
    assert "Sara Khan" in r[4].reply          # name is remembered within the call
    assert len(brain.schedule.find_by_name("sara khan", NOW.date())) == 2


def test_double_booking_prevented(brain):
    d, slots = free_day_and_slots(brain)
    brain.schedule.book("Someone Else", "cleaning", d, slots[0])
    _, r = call(brain, f"cleaning on {d:%B} {d.day} at {slots[0].hour}")
    assert r[0].state == "offering"


def test_goodbye_after_booking(brain):
    d, slots = free_day_and_slots(brain)
    s, r = call(brain, f"cleaning on {d:%B} {d.day} at {slots[0].hour}", "sara khan", "yes", "no thanks")
    assert r[-1].ended and "Goodbye" in r[-1].reply


def test_every_turn_has_a_trace(brain):
    _, r = call(brain, "book a cleaning")
    assert any(line.startswith("Heard") for line in r[0].trace)
    assert any(line.startswith("Decision") or line.startswith("Next") for line in r[0].trace)
