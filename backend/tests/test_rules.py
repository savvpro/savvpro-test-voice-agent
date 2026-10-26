import pytest

from app.nlu.normalizer import normalize
from app.nlu.rules import RULE_CONFIDENCE, match_rules


def rule_intent(text: str) -> str | None:
    match = match_rules(normalize(text))
    return match.intent if match else None


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        # emergency
        ("I have chest pain", "emergency"),
        ("my father is having a heart attack", "emergency"),
        ("I can't breathe", "emergency"),
        ("she cannot breathe properly", "emergency"),
        ("he has difficulty breathing", "emergency"),
        ("she is bleeding heavily", "emergency"),
        ("he is unconscious", "emergency"),
        ("my mother collapsed", "emergency"),
        ("my baby is choking", "emergency"),
        ("this is an emergency", "emergency"),
        ("I need an ambulance", "emergency"),
        # emergency wins over everything, even inside a booking request
        ("book cardiology, I have chest pain right now", "emergency"),
        # human agent
        ("I want to talk to a human", "human_agent"),
        ("can I speak to a real person", "human_agent"),
        ("connect me to the receptionist", "human_agent"),
        ("transfer the call please", "human_agent"),
        ("operator", "human_agent"),
        ("kisi insaan se baat karwa dein", "human_agent"),
        ("I don't want to talk to a machine", "human_agent"),
        # abort
        ("never mind", "abort"),
        ("nevermind", "abort"),
        ("forget it", "abort"),
        ("ok forget about it", "abort"),
        ("start over", "abort"),
        ("rehne do", "abort"),
        ("never mind I'll call later", "abort"),
        # repeat
        ("can you repeat that", "repeat"),
        ("say that again", "repeat"),
        ("what?", "repeat"),
        ("sorry?", "repeat"),
        ("pardon", "repeat"),
        ("I didn't catch that", "repeat"),
        ("dobara bolein", "repeat"),
        # goodbye
        ("bye", "goodbye"),
        ("ok bye", "goodbye"),
        ("allah hafiz", "goodbye"),
        ("that's all thank you", "goodbye"),
        ("no that's it", "goodbye"),
        ("thank you bye", "goodbye"),
        # thank you
        ("thank you", "thank_you"),
        ("thanks a lot", "thank_you"),
        ("shukriya", "thank_you"),
        ("thank you so much", "thank_you"),
        # greet
        ("hello", "greet"),
        ("hi there", "greet"),
        ("assalam o alaikum", "greet"),
        ("Assalamualaikum", "greet"),
        ("good morning", "greet"),
        # deny
        ("no", "deny"),
        ("No.", "deny"),
        ("nope", "deny"),
        ("no thanks", "deny"),
        ("no no", "deny"),
        ("nahi", "deny"),
        ("that's wrong", "deny"),
        ("not correct", "deny"),
        # affirm
        ("yes", "affirm"),
        ("Yes please", "affirm"),
        ("yeah sure", "affirm"),
        ("okay", "affirm"),
        ("that's correct", "affirm"),
        ("haan ji", "affirm"),
        ("ji haan theek hai", "affirm"),
        ("yes book it", "affirm"),
        ("sounds good", "affirm"),
    ],
)
def test_rule_fires(text, intent):
    assert rule_intent(text) == intent


@pytest.mark.parametrize(
    "text",
    [
        # "no" must not fire inside other words or as part of a longer request
        "I don't know",
        "now",
        "not now",
        "nobody told me",
        "no, make it Friday",
        "no wait 4pm instead",
        # "yes" with a change attached is for the classifier
        "yes but change the time to 4",
        "ok so I want to book",
        # greetings followed by a request
        "hello I want to book an appointment",
        "hi can I see a dermatologist",
        # sorry + correction is a change, not a repeat
        "sorry I meant Thursday",
        "what time do you open",
        # negated / historical symptoms are not emergencies
        "I have no chest pain, just a checkup",
        "my father had a heart attack last year, he needs a cardiologist",
        "is the clinic open for non emergency visits",
        # ordinary booking talk
        "I want to book a cardiologist",
        "cancel my appointment",
        "thank you for booking, can I also ask about hours",
        "",
    ],
)
def test_rule_does_not_fire(text):
    assert rule_intent(text) is None


def test_rule_confidence():
    match = match_rules("yes")
    assert match is not None
    assert match.confidence == RULE_CONFIDENCE
    assert match.pattern
