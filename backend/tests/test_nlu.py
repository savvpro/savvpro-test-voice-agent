from datetime import date, time

import pytest

from app import nlu

TODAY = date(2026, 10, 26)  # a Monday


def ex(text, awaiting=None):
    return nlu.extract(nlu.normalize(text), TODAY, awaiting)


@pytest.mark.parametrize("text,expected", [
    ("3pm", time(15, 0)), ("3 pm", time(15, 0)), ("3:30 pm", time(15, 30)),
    ("15:00", time(15, 0)), ("at 3", time(15, 0)), ("at 10", time(10, 0)),
    ("ten am", time(10, 0)), ("at ten", time(10, 0)), ("half past three", time(15, 30)),
    ("quarter to four", time(15, 45)), ("noon", time(12, 0)), ("9 a.m.", time(9, 0)),
    ("3 o'clock", time(15, 0)),
])
def test_parse_time(text, expected):
    assert nlu.parse_time(nlu.normalize(text)) == expected


def test_day_numbers_are_not_times():
    assert nlu.parse_time(nlu.normalize("on the 28th")) is None
    assert nlu.parse_time(nlu.normalize("october 28")) is None


@pytest.mark.parametrize("text,expected", [
    ("today", date(2026, 10, 26)), ("tomorrow", date(2026, 10, 27)),
    ("day after tomorrow", date(2026, 10, 28)), ("friday", date(2026, 10, 30)),
    ("monday", date(2026, 11, 2)), ("this monday", date(2026, 10, 26)),
    ("next tuesday", date(2026, 11, 3)), ("october 30th", date(2026, 10, 30)),
    ("30 october", date(2026, 10, 30)), ("the 28th", date(2026, 10, 28)),
    ("january 5", date(2027, 1, 5)),
])
def test_parse_day(text, expected):
    assert nlu.parse_day(nlu.normalize(text), TODAY) == expected


def test_invalid_date_is_ignored():
    assert nlu.parse_day(nlu.normalize("february 30"), TODAY) is None


def test_month_word_may_is_not_a_date():
    assert ex("may I book a cleaning").day is None


def test_services_and_period():
    e = ex("I need a cleaning tomorrow afternoon")
    assert (e.service, e.period, e.day) == ("cleaning", "afternoon", date(2026, 10, 27))


def test_period_ignored_when_time_given():
    assert ex("tomorrow morning at 10").period is None


def test_good_morning_is_not_a_time_of_day():
    e = ex("Good morning, I'd like a checkup")
    assert e.period is None and e.service == "checkup"


def test_names():
    assert ex("my name is sara khan").name == "Sara Khan"
    assert ex("this is urgent").name is None
    assert ex("I'm looking for a cleaning").name is None
    assert ex("I'm sara", awaiting="name").name == "Sara"
    assert nlu.bare_name("sara khan") == "Sara Khan"
    assert nlu.bare_name("tomorrow") is None


def test_emergency():
    assert ex("my face is swollen and bleeding").emergency
    assert not ex("I'd like a checkup").emergency


@pytest.mark.parametrize("text,intent", [
    ("I want to cancel my appointment", "cancel"),
    ("can I reschedule", "reschedule"), ("please move my appointment", "reschedule"),
    ("I'd like to book", "book"), ("what are your hours", "hours"),
    ("let me talk to a real person", "human"), ("say that again", "repeat"),
    ("no thanks goodbye", "goodbye"), ("banana", None),
])
def test_intents(text, intent):
    assert nlu.detect_intent(nlu.normalize(text)) == intent


def test_yes_no_and_ordinals():
    assert nlu.yes_no("yes please") == "yes" and nlu.yes_no("no") == "no"
    assert nlu.yes_no("nope not right") == "no" and nlu.yes_no("hmm") is None
    assert nlu.ordinal_choice("the second one") == 1 and nlu.ordinal_choice("whichever") == 0
