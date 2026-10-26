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
    assert parse("I'm Sara Lee", TODAY).entities.name == "Sara Lee"
    assert parse("I'm looking for a doctor", TODAY).entities.name is None
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
