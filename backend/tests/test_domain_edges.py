from datetime import UTC, datetime

import pytest

from lost_property.domain.dialogue import respond
from lost_property.domain.extraction import extract
from lost_property.domain.models import Conversation, Fields, FoundItem, Message, Receipt

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "text,want",
    [
        ("today", "2026-10-26"),
        ("2026-10-24", "2026-10-24"),
        ("Monday", "2026-10-26"),
        ("last Monday", "2026-10-19"),
        ("Sunday", "2026-10-25"),
        ("25 October", "2026-10-25"),
    ],
)
def test_dates_have_explicit_repeatable_meaning(text, want):
    assert extract(text, NOW).values["lost_date"] == want


@pytest.mark.parametrize("text", ["2026-10-27", "2026-02-30"])
def test_future_and_impossible_iso_dates_are_not_guessed(text):
    assert extract(text, NOW).problem == "lost_date"


def test_declining_restart_keeps_the_current_search():
    state = Conversation(restart_pending=True, fields=Fields(category="phone"))
    result = respond(state, "no", [], NOW)
    assert result.conversation.fields.category == "phone"
    assert not result.conversation.restart_pending


def test_empty_restart_needs_no_discard_confirmation():
    result = respond(Conversation(), "restart", [], NOW)
    assert not result.conversation.restart_pending
    assert result.conversation.fields.category is None


def test_cancel_does_not_promise_to_delete_a_submitted_case():
    receipt = Receipt(reference="LF-EXISTING", kind="claim", status="pending_review")
    result = respond(Conversation(state="completed", receipt=receipt), "cancel", [], NOW)
    assert result.conversation.receipt == receipt
    assert "remains with staff" in result.reply


def test_cancelled_search_cannot_silently_resume():
    result = respond(Conversation(state="cancelled"), "a black bag", [], NOW)
    assert result.conversation.fields.category is None
    assert result.conversation.state == "cancelled"


def test_no_declines_confirmation_without_effect():
    state = Conversation(
        state="confirming", proposal="lost_report", fields=Fields(category="wallet")
    )
    result = respond(state, "no", [], NOW)
    assert result.effect is None
    assert result.conversation.proposal is None


def test_unclear_confirmation_does_not_create_an_effect():
    state = Conversation(state="confirming", proposal="lost_report")
    result = respond(state, "possibly", [], NOW)
    assert result.effect is None
    assert result.trace.rule == "confirm_clarify"


def test_repeat_reuses_the_last_actual_prompt():
    state = Conversation(transcript=[Message(role="assistant", text="Where did you last have it?")])
    result = respond(state, "repeat", [], NOW)
    assert result.reply == "Where did you last have it?"


def test_ambiguous_category_is_clarified():
    result = respond(Conversation(), "a phone or wallet", [], NOW)
    assert result.conversation.asked == "category"


def test_prevolunteered_private_fact_can_support_a_claim_without_revealing_more():
    item = FoundItem(
        id="one",
        category="bag",
        colour="black",
        location="food court",
        description="two compartments",
        found_date="2026-10-25",
        private_facts=[["yellow duck keychain"], ["PRIVATE-UNVOLUNTEERED-SENTINEL"]],
    )
    result = respond(
        Conversation(),
        "black bag two compartments food court yesterday yellow duck keychain",
        [item],
        NOW,
    )
    assert result.conversation.proposal == "claim"
    assert "SENTINEL" not in result.reply


def test_similar_candidates_produce_a_distinguishing_public_question():
    items = [
        FoundItem(
            id="a",
            category="bag",
            colour="black",
            location="food court",
            description="backpack",
            found_date="2026-10-25",
        ),
        FoundItem(
            id="b",
            category="bag",
            colour="red",
            location="food court",
            description="backpack",
            found_date="2026-10-25",
        ),
    ]
    result = respond(Conversation(), "a bag food court yesterday", items, NOW)
    assert result.conversation.asked == "colour"
    assert result.effect is None


def test_caller_can_prefer_a_safe_candidate_without_bypassing_checks():
    items = [
        FoundItem(
            id="a",
            category="bag",
            colour="black",
            location="food court",
            description="backpack",
            found_date="2026-10-25",
        ),
        FoundItem(
            id="b",
            category="bag",
            colour="red",
            location="food court",
            description="backpack",
            found_date="2026-10-25",
        ),
    ]
    initial = respond(Conversation(), "a bag food court yesterday", items, NOW)
    preferred = respond(initial.conversation, "Option 2", items, NOW)
    assert preferred.conversation.selection == "b"
    assert preferred.effect is None
    assert preferred.conversation.proposal is None


def test_ambiguous_corrected_date_clears_the_old_confirmed_value():
    state = Conversation(
        state="confirming",
        fields=Fields(category="bag", lost_date="2026-10-25"),
        proposal="claim",
        selection="old",
    )
    corrected = respond(state, "actually 03/04/2026", [], NOW)
    assert corrected.conversation.fields.lost_date is None
    assert corrected.conversation.asked == "lost_date"
    assert corrected.effect is None


def test_unsupported_category_does_not_loop_forever():
    result = respond(Conversation(), "a laptop", [], NOW)
    result = respond(result.conversation, "a laptop", [], NOW)
    result = respond(result.conversation, "a laptop", [], NOW)
    assert result.conversation.state == "cancelled"
    assert result.effect is None


def test_identifying_answer_can_correct_the_item_colour_without_actually_keyword():
    from lost_property.persistence.fixtures import demo_items

    items = demo_items(NOW.date())
    initial = respond(Conversation(), "black jansport backpack food court yesterday", items, NOW)
    changed = respond(initial.conversation, "It is red with a yellow duck keychain", items, NOW)
    assert changed.conversation.fields.colour == "red"
    assert changed.conversation.proposal != "claim"
    assert changed.effect is None


def test_identifying_fact_cannot_promote_an_unqualified_runner_up():
    from lost_property.persistence.fixtures import demo_items

    items = demo_items(NOW.date())
    initial = respond(Conversation(), "black jansport backpack food court yesterday", items, NOW)
    changed = respond(initial.conversation, "green glasses case", items, NOW)
    assert changed.conversation.proposal != "claim"
    assert changed.effect is None
