import pytest

from app.nlu.intents import understand, wants_to_skip
from app.nlu.normalize import normalize


@pytest.mark.parametrize(
    "text, intent",
    [
        ("I'd like to book a cleaning", "book"),
        ("can I make an appointment", "book"),
        ("I need to reschedule my appointment", "reschedule"),
        ("please cancel my appointment", "cancel_appointment"),
        ("I have a really bad toothache", "emergency"),
        ("what are your hours", "hours"),
        ("where are you located", "location"),
        ("do you take Delta insurance", "insurance"),
        ("sorry can you say that again", "repeat"),
        ("let's start over", "restart"),
        ("can I talk to a real person", "human"),
        ("yes that works", "affirm"),
        ("no", "deny"),
        ("that's all, bye", "goodbye"),
        ("purple monkey dishwasher", None),
    ],
)
def test_intents(text, intent):
    assert understand(normalize(text)).intent == intent


def test_details():
    u = understand(normalize("my name is Jane Doe and my number is 555 123 4567, I need a filling"))
    assert u.name == "Jane Doe"
    assert u.phone == "5551234567"
    assert u.service == "filling"


def test_choice_and_correction():
    assert understand("the second one").choice == 2
    assert understand("actually make it 4").correction is True


@pytest.mark.parametrize(
    "text, phone",
    [
        ("555 123 4567", "5551234567"),
        ("135 567454 2132", "1355674542132"),  # any grouping, any length from 7 to 15
        ("+44 20 7946 0000", "442079460000"),
        ("(555) 123-4567", "5551234567"),
        ("my number is 5551234", "5551234"),
        ("tomorrow at 10 am, 555 222 3333", "5552223333"),
        ("room 12345", None),  # too short to be a phone number
        ("tomorrow at 10", None),
    ],
)
def test_phone_in_any_format(text, phone):
    assert understand(normalize(text)).phone == phone


@pytest.mark.parametrize("text", ["skip", "no", "i'd rather not", "no thanks", "i don't want to give it", "book it without"])
def test_skip_phone(text):
    assert wants_to_skip(normalize(text))


@pytest.mark.parametrize("text", ["555 123 4567", "jane doe", "sure"])
def test_not_skip_phone(text):
    assert not wants_to_skip(normalize(text))
