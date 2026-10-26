import pytest
from app.brain.nlu import detect_intents, detect_service, normalize


CASES = [
    ("Hey, how are you?", {"greeting"}, set()),
    ("Hi", {"greeting"}, set()),
    ("Hello, I want to book an appointment for tomorrow", {"greeting", "book"}, set()),
    ("Hello my name is Bob and what are your timings", {"greeting", "ask_hours"}, set()),

    ("I need to see a dentist, my tooth is very painful", {"book", "urgent"}, set()),
    ("I want to extract an infected wisdom tooth of my mother", {"urgent"}, {"ask_price"}),
    ("What are the charges for molar extraction?", {"ask_price"}, {"book"}),
    ("What is your clinic time on Saturday?", {"ask_hours"}, set()),
    ("Are you available at 9am tomorrow?", {"ask_availability"}, {"ask_hours"}),
    ("Sounds good, I will be there at 11am", {"affirm"}, {"deny"}),
    ("Yes, confirmed", {"affirm"}, {"deny"}),
    ("Yes but make it 1pm", {"affirm"}, {"deny"}),
    ("Why don't you give me some discount for 8k?", {"ask_discount"}, set()),
    ("Can you make it 8k?", {"ask_discount"}, {"affirm"}),
    ("That's too expensive, can you reduce it?", {"ask_discount"}, {"ask_price"}),

    ("I don't know", set(), {"deny"}),
    ("I know a good bookstore", set(), {"book", "deny"}),
    ("This is a highly unusual case", set(), {"greeting"}),
    ("I am open to any time", set(), {"ask_hours"}),

    ("YES!!!", {"affirm"}, set()),
    ("O.K.", {"affirm"}, set()),
    ("no no no", {"deny"}, set()),
    ("Sorry, say that again", {"repeat"}, {"goodbye"}),
    ("What did you ask?", {"repeat"}, set()),
    ("Never mind", {"goodbye"}, {"deny"}),
    ("Thanks, bye!", {"goodbye", "thanks"}, set()),
    ("No thanks, bye", {"goodbye"}, set()),
    ("Can I talk to a real person?", {"human"}, set()),
    ("I have severe pain and swelling, it is an emergency", {"urgent"}, set()),
    ("I want to cancel my appointment", {"cancel"}, set()),
    ("Can I move my appointment to Friday?", {"reschedule"}, set()),
    ("haan ji theek hai", {"affirm"}, set()),
    ("nahi", {"deny"}, set()),

    ("Can you do it for 8000 rupees?", {"ask_discount"}, {"affirm"}),
   ("I want an appointment on 27 October 2026", {"book"}, {"ask_discount"}),
]

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Hey, how are you?", "hey how are you"),
        ("I'll be there at 5 P.M.", "ill be there at 5 pm"),
        ("It's  Bob!", "its bob"),
        ("at 5:30", "at 5:30"),
        ("Hey,hello", "hey hello"),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("I want an infected wisdom tooth removed", "wisdom tooth extraction"),
        ("how much is a general check-up", "checkup"),
        ("I have a cavity", "filling"),
        ("I need a root canal", "root canal"),
        ("what time do you open", None),
    ],
)
def test_detect_service(text, expected):
    assert detect_service(text) == expected

@pytest.mark.parametrize("text, must_have, must_not", CASES)
def test_detect_intents(text, must_have, must_not):
    found = detect_intents(text)
    assert must_have <= found, f"missing {must_have - found}, found {found}"
    assert not (must_not & found), f"unexpected {must_not & found}, found {found}"


def test_gibberish_finds_nothing():
    assert detect_intents("asdf qwer") == set()
    assert detect_intents("uhh hmm") == set()