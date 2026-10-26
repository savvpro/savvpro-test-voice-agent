from datetime import date, datetime, time

import pytest

from app.nlu.entities import extract_entities
from app.nlu.normalizer import normalize

# Wednesday 9 January 2030, 10:00 clinic time
NOW = datetime(2030, 1, 9, 10, 0)


def extract(text: str, expected_slot: str | None = None, now: datetime = NOW):
    return extract_entities(normalize(text), now=now, expected_slot=expected_slot)


# --- dates ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("today", date(2030, 1, 9)),
        ("tomorrow", date(2030, 1, 10)),
        ("tmrw", date(2030, 1, 10)),
        ("day after tomorrow", date(2030, 1, 11)),
        ("friday", date(2030, 1, 11)),
        ("on Monday", date(2030, 1, 14)),
        ("next monday", date(2030, 1, 14)),
        ("this friday", date(2030, 1, 11)),
        ("coming thursday", date(2030, 1, 10)),
        ("this wednesday", date(2030, 1, 9)),  # today is Wednesday
        ("wednesday", date(2030, 1, 16)),  # bare weekday = next occurrence
        ("in 3 days", date(2030, 1, 12)),
        ("in a week", date(2030, 1, 16)),
        # day-only: upcoming, never in the past
        ("the 15th", date(2030, 1, 15)),
        ("the 9th", date(2030, 1, 9)),
        ("the 5th", date(2030, 2, 5)),
        ("the fifth", date(2030, 2, 5)),
        ("on the twenty first", date(2030, 1, 21)),
        ("the 5th of next month", date(2030, 2, 5)),
        # day + month
        ("5th of january", date(2031, 1, 5)),
        ("january 20th", date(2030, 1, 20)),
        ("20 jan", date(2030, 1, 20)),
        ("the third of february", date(2030, 2, 3)),
        ("5/2", date(2030, 2, 5)),  # DMY
    ],
)
def test_dates(text, expected):
    assert extract(text).date == expected


def test_day_only_skips_months_without_that_day():
    now = datetime(2030, 1, 31, 10, 0)
    assert extract("the 30th", now=now).date == date(2030, 3, 30)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("actually make it friday", date(2030, 1, 11)),
        ("not monday, friday", date(2030, 1, 11)),
        ("instead of monday make it thursday", date(2030, 1, 10)),
        ("move it from monday to friday", date(2030, 1, 11)),
    ],
)
def test_corrections_pick_the_new_date(text, expected):
    assert extract(text).date == expected


@pytest.mark.parametrize(
    "text", ["I sat in the waiting room", "the sun is out", "may I book", "march on", "3"]
)
def test_no_false_dates(text):
    assert extract(text).date is None


# --- times ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("at 3 pm", time(15, 0)),
        ("3pm", time(15, 0)),
        ("10 am", time(10, 0)),
        ("15:00", time(15, 0)),
        ("at 3:30", time(15, 30)),
        ("at 10:30", time(10, 30)),
        ("half past two", time(14, 30)),
        ("quarter to eleven", time(10, 45)),
        ("at three o'clock", time(15, 0)),
        ("at 3", time(15, 0)),  # clinic hours: 3 means afternoon
        ("at 11", time(11, 0)),
        ("around 4", time(16, 0)),
        ("12 pm", time(12, 0)),
        ("at noon", time(12, 0)),
        ("10 in the morning", time(10, 0)),
        ("4 in the afternoon", time(16, 0)),
        ("no wait 4pm instead", time(16, 0)),
        ("not 10 make it 11", time(11, 0)),
        ("can you change it to 4", time(16, 0)),
    ],
)
def test_times(text, expected):
    assert extract(text).time == expected


def test_bare_number_is_a_time_only_when_asked_for_one():
    assert extract("3", expected_slot="time").time == time(15, 0)
    assert extract("3 please", expected_slot="time").time == time(15, 0)
    assert extract("3").time is None
    assert extract("3", expected_slot="date").time is None


@pytest.mark.parametrize(
    "text",
    [
        "the 5th",
        "in 3 days",
        "I have 2 kids",
        "go to 2 doctors",
        "03001234567",
        "sc 4f7k",
        "for 5 people",
    ],
)
def test_no_false_times(text):
    assert extract(text).time is None


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("in the morning", "morning"),
        ("afternoon is better", "afternoon"),
        ("after lunch", "after lunch"),
        ("late afternoon", "late afternoon"),
        ("early morning please", "early morning"),
        ("evening", "evening"),
        ("not morning, afternoon", "afternoon"),
    ],
)
def test_time_of_day(text, label):
    tod = extract(text).time_of_day
    assert tod is not None
    assert tod.label == label
    assert tod.start < tod.end


# --- combined -------------------------------------------------------------


def test_several_slots_in_one_sentence():
    e = extract("Book me with a dermatologist next Monday at 10 am")
    assert e.department == "Dermatology"
    assert e.date == date(2030, 1, 14)
    assert e.time == time(10, 0)


def test_doctor_date_and_time_of_day():
    e = extract("with dr saima tomorrow morning")
    assert e.doctor == "Dr. Saima Rauf"
    assert e.date == date(2030, 1, 10)
    assert e.time_of_day.label == "morning"
    assert e.time is None


def test_unknown_department():
    e = extract("do you have a dentist")
    assert e.department is None
    assert e.unknown_department == "dentist"


# --- phone ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("03001234567", "03001234567"),
        ("my number is 0300-1234567", "03001234567"),
        ("0321 555 1234", "03215551234"),
        ("+92 300 1234567", "03001234567"),
        ("923001234567", "03001234567"),
        ("zero three zero zero five five five one two three four", "03005551234"),
        ("plus nine two three three three five five five zero one nine nine", "03335550199"),
    ],
)
def test_phone(text, expected):
    assert extract(text).phone == expected


@pytest.mark.parametrize("text", ["12345", "0300123", "04235551234", "the year 2030"])
def test_not_a_phone(text):
    assert extract(text).phone is None


# --- booking ref ----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("SC-4F7K", "SC-4F7K"),
        ("my reference is sc 7k2m", "SC-7K2M"),
        ("S C 4 F 7 K", "SC-4F7K"),
        ("es see four f seven k", None),  # too garbled: no guess
        ("ref sc9p3q please", "SC-9P3Q"),
        ("sc 4 f 7 k", "SC-4F7K"),
        ("SC-ABCD", "SC-ABCD"),
    ],
)
def test_booking_ref(text, expected):
    assert extract(text).booking_ref == expected


@pytest.mark.parametrize(
    "text",
    ["my phone screen is broken", "my son's school", "i'm scared", "scheduled", "scan report"],
)
def test_words_starting_with_sc_are_not_booking_refs(text):
    assert extract(text).booking_ref is None


# --- name -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("my name is Ali Raza", "Ali Raza"),
        ("my name's Sana", "Sana"),
        ("name is omar farooq and my number is 03001234567", "Omar Farooq"),
        ("this is Sana Malik speaking", "Sana Malik"),
        ("I'm Ali Raza calling to book", "Ali Raza"),
        ("mera naam Ayesha hai", "Ayesha"),
        ("call me Hamza", "Hamza"),
        ("my name is Bilal Aslam", "Bilal Aslam"),  # same as a doctor; still the caller
    ],
)
def test_name(text, expected):
    assert extract(text).patient_name == expected


def test_name_is_not_mistaken_for_doctor():
    e = extract("my name is Bilal Aslam")
    assert e.doctor is None


@pytest.mark.parametrize(
    "text",
    [
        "I am having fever",
        "I'm calling to book",
        "I am looking for a dermatologist",
        "this is for my mother",
        "this is urgent",
        "I'm not sure",
        "I am free on monday",
        "I am pregnant",
    ],
)
def test_no_false_names(text):
    assert extract(text).patient_name is None


def test_bare_name_only_when_asked_for_one():
    assert extract("sana malik", expected_slot="patient_name").patient_name == "Sana Malik"
    assert extract("sana malik").patient_name is None
    assert extract("yes", expected_slot="patient_name").patient_name is None
    assert extract("cardiology", expected_slot="patient_name").patient_name is None


def test_empty_text():
    assert extract("").found() == {}
