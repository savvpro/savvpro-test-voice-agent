import datetime as dt

from app.brain.models import Intent
from app.brain.nlu import parse

TODAY = dt.date(2026, 11, 2)


def test_intents():
    assert parse("I want to book an appointment", TODAY).primary_intent == Intent.BOOK
    assert parse("can I reschedule my appointment", TODAY).primary_intent == Intent.RESCHEDULE
    assert parse("I need to cancel", TODAY).primary_intent == Intent.CANCEL
    assert parse("move my appointment to friday", TODAY).primary_intent == Intent.RESCHEDULE
    assert parse("blah blah", TODAY).primary_intent is None


def test_multiple_entities_in_one_sentence():
    p = parse("book a dentist appointment tomorrow at 4 pm", TODAY)
    assert (p.specialty, p.day, p.at) == ("dental", dt.date(2026, 11, 3), dt.time(16, 0))


def test_correction_keeps_the_wanted_side_of_not():
    assert parse("no I said 4 PM not 4 AM", TODAY).at == dt.time(16, 0)
    assert parse("not 4 AM, 4 PM", TODAY).at == dt.time(16, 0)
    assert parse("friday instead of thursday", TODAY).day == dt.date(2026, 11, 6)


def test_yes_no_detection():
    assert parse("yes please", TODAY).yes
    assert parse("no that's wrong", TODAY).no
    assert not parse("that's not right", TODAY).yes  # "right" must not count as yes here


def test_names():
    assert parse("my name is Sara Khan", TODAY).name == "Sara Khan"
    assert parse("Sara Malik please", TODAY, expecting="name").name == "Sara Malik"
    assert parse("I'm zainab noor", TODAY, expecting="name").name == "Zainab Noor"
    assert parse("yes", TODAY, expecting="name").name is None
    assert parse("tomorrow at 4", TODAY, expecting="name").name is None
    assert parse("it's tomorrow", TODAY).name is None  # weak lead ignored unless a name is expected


def test_surname_khan_is_not_the_doctor():
    assert parse("my name is Sara Khan", TODAY).specialty is None
    assert parse("I want to see doctor Khan", TODAY).specialty == "general"


def test_flags():
    assert parse("let me talk to a human", TODAY).human
    assert parse("can you repeat that", TODAY).repeat
    assert parse("let's start over", TODAY).restart
    assert parse("never mind", TODAY).abort
    assert parse("that's all, bye", TODAY).goodbye
    assert parse("what are your opening hours", TODAY).faq == "hours"
    assert parse("where are you located", TODAY).faq == "location"


def test_ordinal_choice():
    assert parse("the second one", TODAY, expecting="offer").choice == 2
    assert parse("the last one", TODAY, expecting="offer").choice == -1


def test_phone_digits_do_not_leak_into_time():
    p = parse("zero three two one one two three four five six seven", TODAY, expecting="phone")
    assert p.phone == "03211234567" and p.at is None
