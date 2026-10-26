import json
from pathlib import Path

from app.conversation.normalizer import normalize


def test_noisy_transcript_corpus() -> None:
    fixtures = json.loads((Path(__file__).parent / "fixtures/noisy_transcripts.json").read_text())
    for case in fixtures:
        assert normalize(case["raw"], case["context"]) == case["normalized"]


def test_homophones_not_changed_in_ordinary_prose() -> None:
    assert normalize("I need to wait for Friday", "service") == "i need to wait for friday"


def test_dotted_meridiem_is_normalized() -> None:
    assert normalize("12:00 p.m.", "time") == "12:00 pm"
    assert normalize("12 p.m.", "time") == "12 pm"
