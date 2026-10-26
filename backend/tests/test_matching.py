from datetime import date

from lost_property.domain.matching import rank
from lost_property.domain.models import Fields, FoundItem


def item(**changes):
    return FoundItem.model_validate(
        {
            "id": "bag-1",
            "category": "bag",
            "description": "two compartments",
            "colour": "black",
            "location": "food court",
            "found_date": "2026-10-25",
            "private_facts": [["yellow duck keychain"]],
            **changes,
        }
    )


def test_scores_public_evidence_without_double_counting():
    matches = rank(
        Fields(
            category="bag",
            colour="black",
            location="food court",
            description="black backpack near food court",
        ),
        [item()],
    )
    assert matches[0].score == 55
    assert matches[0].signals == {"category": 30, "description": 0, "colour": 15, "location": 10}


def test_excludes_returned_incompatible_and_impossible_items():
    fixtures = [
        item(id="returned", status="returned"),
        item(id="wrong", category="phone"),
        item(id="old", found_date=date(2026, 10, 24)),
        item(),
    ]
    matches = rank(Fields(category="bag", lost_date="2026-10-25"), fixtures)
    assert [match.item_id for match in matches] == ["bag-1"]


def test_uncertain_colour_neither_rewards_nor_penalizes():
    matches = rank(Fields(category="bag", colour="blue", uncertain=["colour"]), [item()])
    assert matches[0].score == 30


def test_private_facts_are_not_used_for_retrieval():
    matches = rank(Fields(category="bag", description="yellow duck keychain"), [item()])
    assert matches[0].score == 30


def test_ties_have_stable_order_without_implying_confidence():
    matches = rank(Fields(category="bag"), [item(id="z"), item(id="a")])
    assert [match.item_id for match in matches] == ["a", "z"]
