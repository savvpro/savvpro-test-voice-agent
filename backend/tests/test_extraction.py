from datetime import UTC, datetime

import pytest

from lost_property.domain.extraction import extract
from lost_property.domain.normalization import normalize

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "text,want",
    [("A RUCKSACK!", "a backpack"), ("near restaurants", "near food court"), ("navy", "dark blue")],
)
def test_normalizes_ordinary_vocabulary(text, want):
    assert normalize(text) == want


def test_extracts_multiple_facts_in_one_turn():
    result = extract("My black rucksack was near the restaurants yesterday", NOW)
    assert result.values == {
        "category": "bag",
        "colour": "black",
        "location": "food court",
        "lost_date": "2026-10-25",
    }


def test_negated_colour_is_not_selected():
    assert extract("not blue, black", NOW).values["colour"] == "black"


def test_uncertain_colour_stays_uncertain():
    assert "colour" in extract("maybe blue", NOW).uncertain


@pytest.mark.parametrize("text", ["03/04/2026", "tomorrow", "31 February 2026"])
def test_ambiguous_future_and_invalid_dates_need_clarification(text):
    assert extract(text, NOW).problem == "lost_date"


def test_unknown_answer_marks_the_expected_field_unknown():
    assert extract("I don't know", NOW, "location").unknown == ["location"]


def test_conflicting_categories_need_clarification():
    assert extract("a phone or a wallet", NOW).problem == "category"
