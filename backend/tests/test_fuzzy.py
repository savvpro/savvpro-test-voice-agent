import pytest

from app.nlu.entities import default_doctor_names
from app.nlu.fuzzy import (
    match_department,
    match_doctor,
    match_intent_keywords,
    match_unknown_department,
)
from app.nlu.normalizer import normalize


@pytest.mark.parametrize(
    ("text", "department"),
    [
        ("cardiology", "Cardiology"),
        ("heart doctor", "Cardiology"),
        ("I need a cardiologist", "Cardiology"),
        ("cardio logy please", "Cardiology"),  # STT split word
        ("kardiology", "Cardiology"),  # STT misspelling
        ("skin doctor", "Dermatology"),
        ("dermatolagy", "Dermatology"),
        ("derma", "Dermatology"),
        ("kids doctor", "Pediatrics"),
        ("paediatrician", "Pediatrics"),
        ("my child has fever", "Pediatrics"),  # earliest of two symptom words
        ("child specialist for fever", "Pediatrics"),
        ("bone doctor", "Orthopedics"),
        ("I have back pain", "Orthopedics"),
        ("ENT", "ENT"),
        ("ear nose throat", "ENT"),
        ("gynae", "Gynecology"),
        ("lady doctor", "Gynecology"),
        ("general physician", "General Medicine"),
        ("I have fever", "General Medicine"),
        # corrections skip the negated department
        ("I meant cardiology not dermatology", "Cardiology"),
        ("not dermatology, cardiology", "Cardiology"),
    ],
)
def test_match_department(text, department):
    match = match_department(normalize(text))
    assert match is not None
    assert match.value == department


@pytest.mark.parametrize(
    "text", ["", "I want to book", "next monday at 3", "entire", "the year", "drama"]
)
def test_match_department_none(text):
    assert match_department(normalize(text)) is None


def test_exact_match_scores_higher_than_fuzzy():
    exact = match_department("cardiology")
    fuzzy = match_department("kardiology")
    assert exact.score == 1.0
    assert 0.85 <= fuzzy.score < 1.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [("I need a dentist", "dentist"), ("eye doctor please", "eye doctor"), ("tooth pain", "tooth")],
)
def test_match_unknown_department(text, expected):
    assert match_unknown_department(normalize(text)).value == expected


@pytest.mark.parametrize(
    ("text", "doctor"),
    [
        ("with dr saima", "Dr. Saima Rauf"),
        ("doctor rauf please", "Dr. Saima Rauf"),
        ("Dr. Imran Haider", "Dr. Imran Haider"),
        ("with imran haider", "Dr. Imran Haider"),
        ("dr saema", "Dr. Saima Rauf"),  # STT misspelling
        ("dr mehwish", "Dr. Mehwish Khalid"),
        ("I'd like to see kamran iqbal", "Dr. Kamran Iqbal"),
    ],
)
def test_match_doctor(text, doctor):
    match = match_doctor(normalize(text), default_doctor_names())
    assert match is not None
    assert match.value == doctor


@pytest.mark.parametrize(
    "text",
    ["bilal", "with my son", "dr", "doctor please", "i'm saima", "with usama", "with zainab"],
)
def test_match_doctor_needs_trigger_or_full_name(text):
    assert match_doctor(normalize(text), default_doctor_names()) is None


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("what is your address", "clinic_location"),
        ("opening hours", "clinic_hours"),
        ("cancle my apointment", "cancel_appointment"),
        ("reschedule my appointment", "reschedule_appointment"),
    ],
)
def test_match_intent_keywords(text, intent):
    scores = match_intent_keywords(normalize(text))
    assert scores[0][0] == intent
    assert scores[0][1] >= 0.8


def test_match_intent_keywords_empty():
    assert match_intent_keywords("") == []
