from datetime import date, time

import pytest

from app.nlu import Intent, Slot, parse

TODAY = date(2026, 10, 26)


def test_past_year_is_dob() -> None:
    e = parse("I was born March 4 1990", TODAY).entities
    assert e.dob == date(1990, 3, 4)
    assert e.date is None


def test_dob_when_expecting() -> None:
    e = parse("03/04/1990", TODAY, Slot.DOB).entities
    assert e.dob == date(1990, 3, 4) and e.date is None


@pytest.mark.parametrize(
    "text,intent",
    [
        ("I'd like to book an appointment", Intent.BOOK),
        ("I need to cancel", Intent.CANCEL),
        ("can I move my appointment", Intent.RESCHEDULE),
        ("yes that's right", Intent.AFFIRM),
        ("no", Intent.DENY),
        ("bye", Intent.GOODBYE),
        ("sorry what?", Intent.REPEAT),
        ("help", Intent.HELP),
        ("I have chest pain", Intent.EMERGENCY),
        ("I have chest pain, cancel my appointment", Intent.EMERGENCY),
        ("blah", Intent.UNKNOWN),
    ],
)
def test_intents(text: str, intent: Intent) -> None:
    assert parse(text, TODAY).intent == intent


def test_multi_entity() -> None:
    p = parse("Book me with Dr Khan next Tuesday at 3pm, my name is Sara Lee", TODAY)
    e = p.entities
    assert p.intent == Intent.BOOK
    assert (e.doctor_id, e.date, e.time, e.name) == (
        "khan",
        date(2026, 11, 3),
        time(15),
        "Sara Lee",
    )


def test_fuzzy_doctor() -> None:
    assert parse("doctor nguen", TODAY).entities.doctor_id == "nguyen"
    assert parse("doctor smith", TODAY).entities.doctor_id is None


def test_specialty() -> None:
    assert parse("something for a skin rash", TODAY).entities.specialty == "dermatology"
    assert parse("any doctor is fine", TODAY).entities.any_doctor is True


def test_bare_name_when_expecting() -> None:
    assert parse("sara lee", TODAY, Slot.NAME).entities.name == "Sara Lee"
    assert parse("sara lee", TODAY).entities.name is None
    assert parse("patel", TODAY, Slot.NAME).entities.name == "Patel"


def test_name_phrases() -> None:
    assert parse("I'm Sara Lee", TODAY, Slot.NAME).entities.name == "Sara Lee"
    assert parse("I'm Sara Lee", TODAY).entities.name is None
    assert parse("I'm looking for a doctor", TODAY, Slot.NAME).entities.name is None
    assert parse("this is John", TODAY).entities.name == "John"
    assert parse("is this John?", TODAY).entities.name is None


def test_ref() -> None:
    assert parse("my reference is cln 7k2q", TODAY).entities.ref == "CLN-7K2Q"
    assert parse("C L N 7 K 2 Q", TODAY).entities.ref == "CLN-7K2Q"


def test_choice_and_bare_time() -> None:
    assert parse("the second one", TODAY, Slot.CHOICE).entities.choice == 2
    assert parse("3", TODAY, Slot.CHOICE).entities.choice == 3
    assert parse("the 3:30 one", TODAY, Slot.CHOICE).entities.time == time(15, 30)
    assert parse("3", TODAY, Slot.TIME).entities.time == time(15)


def test_as_dict() -> None:
    d = parse("tomorrow at 3pm", TODAY).entities.as_dict()
    assert d == {"date": "2026-10-27", "time": "15:00"}


@pytest.mark.parametrize(
    "text",
    ["the first available", "just a second", "this is my first visit", "first time patient"],
)
def test_ordinal_words_not_dates(text: str) -> None:
    assert parse(text, TODAY).entities.date is None


def test_choice_ordinals_not_dates() -> None:
    for text, n in [("the first one", 1), ("the second", 2)]:
        e = parse(text, TODAY, Slot.CHOICE).entities
        assert e.choice == n and e.date is None and e.time is None
    assert parse("the fourteenth", TODAY).entities.date == date(2026, 11, 14)


def test_spaced_and_spoken_times() -> None:
    assert parse("3 30 pm", TODAY).entities.time == time(15, 30)
    e = parse("the 2 30 one", TODAY, Slot.CHOICE).entities
    assert e.time == time(14, 30) and e.choice is None
    assert parse("three thirty pm", TODAY).entities.time == time(15, 30)
    assert parse("at three thirty", TODAY).entities.time == time(15, 30)
    assert parse("ten thirty", TODAY, Slot.TIME).entities.time == time(10, 30)
    assert parse("10 30", TODAY, Slot.TIME).entities.time == time(10, 30)
    e = parse("nine in the morning", TODAY).entities
    assert e.time == time(9) and e.part_of_day is None
    e = parse("the one at three", TODAY, Slot.CHOICE).entities
    assert e.time == time(15) and e.choice is None


@pytest.mark.parametrize(
    "text",
    [
        "i am pregnant",
        "i am free on friday",
        "i am available friday",
        "i am worried about my rash",
        "i am bleeding heavily",
    ],
)
def test_i_am_not_a_name(text: str) -> None:
    assert parse(text, TODAY).entities.name is None


def test_bleeding_is_emergency() -> None:
    assert parse("i am bleeding heavily", TODAY).intent == Intent.EMERGENCY
    assert parse("i am bleeding badly", TODAY).intent == Intent.EMERGENCY


def test_spoken_dob() -> None:
    e = parse("march fourth nineteen ninety", TODAY, Slot.DOB).entities
    assert e.dob == date(1990, 3, 4)
    e = parse("march fourth nineteen ninety", TODAY).entities
    assert e.dob == date(1990, 3, 4) and e.date is None
    assert parse("june 1 nineteen eighty five", TODAY).entities.dob == date(1985, 6, 1)
    assert parse("may second two thousand five", TODAY).entities.dob == date(2005, 5, 2)


def test_fillers() -> None:
    assert parse("uh no", TODAY).intent == Intent.DENY
    assert parse("um sara lee", TODAY, Slot.NAME).entities.name == "Sara Lee"
    assert parse("hello", TODAY, Slot.NAME).entities.name is None
    assert parse("thanks", TODAY, Slot.NAME).entities.name is None


def test_affirm_negation_and_future_dob() -> None:
    assert parse("not ok", TODAY).intent != Intent.AFFIRM
    assert parse("not correct", TODAY).intent != Intent.AFFIRM
    assert parse("march 4 2999", TODAY, Slot.DOB).entities.dob is None
