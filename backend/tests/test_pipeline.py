from datetime import date, datetime, time

import pytest

from app.nlu.pipeline import (
    CONTEXT_CONFIDENCE,
    FALLBACK_INTENT,
    FUZZY_THRESHOLD,
    ML_THRESHOLD,
    NLUResult,
    parse,
)
from app.nlu.rules import RULE_CONFIDENCE

NOW = datetime(2030, 1, 9, 10, 0)  # Wednesday


class StubClassifier:
    """Returns fixed predictions so each fusion branch can be forced."""

    def __init__(self, predictions):
        self.predictions = predictions

    def predict(self, normalized_text, top_k=3):
        return self.predictions[:top_k] if normalized_text else []


# --- realistic utterances through the real model ----------------------------


@pytest.mark.parametrize(
    ("text", "expected_slot", "intent"),
    [
        ("Hi, I want to book an appointment with a skin doctor", None, "book_appointment"),
        ("Book me with a dermatologist next Monday at 10 am", None, "book_appointment"),
        ("I need to cancel my appointment, reference SC-4F7K", None, "cancel_appointment"),
        ("can I move my booking to Friday", None, "reschedule_appointment"),
        ("does cardiology have anything thursday", None, "check_availability"),
        ("is dr saima available on monday", None, "check_availability"),
        ("what time do you close on saturday", None, "clinic_hours"),
        ("where is the clinic", None, "clinic_location"),
        ("which departments do you have", None, "list_departments"),
        ("who are the doctors in ENT", None, "list_doctors"),
        ("actually make it Friday", None, "change_request"),
        ("no wait, 4pm instead", "time", "change_request"),
        ("my name is Ali Raza", "patient_name", "inform"),
        ("Sana Malik", "patient_name", "inform"),
        ("zero three zero zero one two three four five six seven", "phone", "inform"),
        ("tomorrow morning", "date", "inform"),
        ("cardio logy", "department", "inform"),
        ("yes please", None, "affirm"),
        ("no", None, "deny"),
        ("I have chest pain", "date", "emergency"),
        ("can I talk to a real person", None, "human_agent"),
        ("never mind", None, "abort"),
        ("what?", None, "repeat"),
        ("thanks bye", None, "goodbye"),
        ("what's the weather today", None, "out_of_scope"),
        ("cancle my apointment", None, "cancel_appointment"),
    ],
)
def test_realistic_utterances(classifier, text, expected_slot, intent):
    result = parse(text, expected_slot=expected_slot, now=NOW, classifier=classifier)
    assert result.intent == intent, result.model_dump()


@pytest.mark.parametrize(
    "text",
    [
        "I need a cardiologist next tuesday morning",  # was nlu_fallback (0.44) before
        "i want a dermatologist on friday afternoon",
        "need ent tomorrow evening",
    ],
)
def test_department_date_and_time_of_day_is_a_booking(classifier, text):
    result = parse(text, now=NOW, classifier=classifier)
    assert (result.intent, result.source) == ("book_appointment", "ml"), result.model_dump()
    assert result.entities.department and result.entities.date and result.entities.time_of_day


def test_entities_are_returned_with_the_intent(classifier):
    result = parse(
        "Book me with a dermatologist next Monday at 10 am", now=NOW, classifier=classifier
    )
    assert result.entities.department == "Dermatology"
    assert result.entities.date == date(2030, 1, 14)
    assert result.entities.time == time(10, 0)
    assert result.normalized_text == "book me with a dermatologist next monday at 10 am"
    assert len(result.alternatives) == 3


def test_result_is_json_serialisable(classifier):
    result = parse("cardiology tomorrow at 3", now=NOW, classifier=classifier)
    data = result.model_dump(mode="json")
    assert data["entities"]["date"] == "2030-01-10"
    assert data["entities"]["time"] == "15:00:00"
    assert NLUResult.model_validate(data) == result


# --- fusion order (stub classifier) -----------------------------------------


def test_rule_beats_confident_classifier():
    stub = StubClassifier([("book_appointment", 0.99)])
    result = parse("yes", now=NOW, classifier=stub)
    assert (result.intent, result.source, result.confidence) == ("affirm", "rule", RULE_CONFIDENCE)
    assert result.rule_pattern
    # alternatives still show what the classifier thought
    assert result.alternatives[0].intent == "book_appointment"


def test_emergency_rule_wins_even_mid_booking():
    stub = StubClassifier([("inform", 0.99)])
    result = parse("cardiology, he can't breathe", expected_slot="department", classifier=stub)
    assert result.intent == "emergency"


def test_ml_used_when_confident():
    stub = StubClassifier([("check_availability", ML_THRESHOLD), ("inform", 0.2)])
    result = parse("anything thursday", now=NOW, classifier=stub)
    assert (result.intent, result.source) == ("check_availability", "ml")


def test_fuzzy_used_when_ml_unsure():
    stub = StubClassifier([("inform", ML_THRESHOLD - 0.01)])
    result = parse("what is your address", now=NOW, classifier=stub)
    assert (result.intent, result.source) == ("clinic_location", "fuzzy")
    assert result.confidence >= FUZZY_THRESHOLD


def test_context_boost_when_expected_slot_filled():
    stub = StubClassifier([("out_of_scope", 0.3)])
    result = parse("3", expected_slot="time", now=NOW, classifier=stub)
    assert (result.intent, result.source, result.confidence) == (
        "inform",
        "context",
        CONTEXT_CONFIDENCE,
    )
    assert result.entities.time == time(15, 0)


def test_time_of_day_fills_time_slot():
    stub = StubClassifier([("out_of_scope", 0.3)])
    result = parse("afternoon", expected_slot="time", now=NOW, classifier=stub)
    assert result.source == "context"


def test_no_context_boost_for_a_different_slot():
    stub = StubClassifier([("out_of_scope", 0.3)])
    result = parse("3", expected_slot="date", now=NOW, classifier=stub)
    assert result.intent == FALLBACK_INTENT
    assert result.source == "fallback"


def test_fallback_when_nothing_is_confident():
    stub = StubClassifier([("greet", 0.25), ("inform", 0.2)])
    result = parse("asdf qwerty zxcv", now=NOW, classifier=stub)
    assert (result.intent, result.source) == (FALLBACK_INTENT, "fallback")
    assert result.confidence == 0.25


@pytest.mark.parametrize("text", ["", "   ", "umm", "uh hmm"])
def test_silence_and_fillers_fall_back(text):
    result = parse(text, now=NOW, classifier=StubClassifier([("greet", 0.9)]))
    assert result.intent == FALLBACK_INTENT
    assert result.confidence == 0.0
    assert result.normalized_text == ""
