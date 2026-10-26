from datetime import date

import pytest

from lost_property.domain.identification import identify
from lost_property.domain.models import FoundItem


def bag(identity="one", facts=None):
    return FoundItem(
        id=identity,
        category="bag",
        description="backpack",
        found_date=date(2026, 10, 26),
        private_facts=facts or [["yellow duck keychain", "yellow duck charm"], ["blue notebook"]],
    )


@pytest.mark.parametrize(
    "text", ["yellow duck keychain", "a yellow duck charm on the zip", "blue notebook"]
)
def test_volunteered_distinguishing_fact_selects_unique_candidate(text):
    assert identify(text, [bag()]) == "one"


@pytest.mark.parametrize(
    "text",
    [
        "yes",
        "yellow",
        "duck",
        "not a yellow duck keychain",
        "no blue notebook",
        "maybe a blue notebook",
    ],
)
def test_agreement_fragments_negation_and_uncertainty_do_not_establish_evidence(text):
    assert identify(text, [bag()]) is None


def test_evidence_shared_by_two_items_is_ambiguous():
    assert identify("blue notebook", [bag(), bag("two")]) is None
