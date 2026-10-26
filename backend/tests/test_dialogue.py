from datetime import UTC, datetime

from lost_property.domain.dialogue import respond
from lost_property.domain.models import Conversation, Fields, FoundItem, Receipt

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)


def test_missing_category_asks_for_item_type():
    result = respond(Conversation(), "I lost something", [], NOW)
    assert result.conversation.asked == "category"
    assert result.effect is None
    assert "bag" in result.reply.lower()


def test_cancel_has_no_effect():
    result = respond(Conversation(), "cancel", [], NOW)
    assert result.conversation.state == "cancelled"
    assert result.effect is None


def test_input_snapshot_is_not_mutated():
    original = Conversation()
    respond(original, "a black backpack", [], NOW)
    assert original.fields.category is None
    assert original.version == 0


def inventory():
    return [
        FoundItem(
            id="one",
            category="bag",
            colour="black",
            location="food court",
            description="two compartments",
            found_date="2026-10-25",
            private_facts=[["yellow duck keychain"], ["blue notebook"]],
        ),
        FoundItem(
            id="two",
            category="bag",
            colour="red",
            location="cinema",
            description="canvas tote",
            found_date="2026-10-25",
            private_facts=[["green glasses case"]],
        ),
    ]


def turn(state, text, items=None):
    return respond(state, text, inventory() if items is None else items, NOW)


def test_likely_match_asks_open_identifying_question_without_disclosure():
    result = turn(Conversation(), "black backpack with two compartments food court yesterday")
    assert result.conversation.state == "identifying"
    assert "yellow" not in result.reply
    assert "duck" not in result.trace.model_dump_json()
    assert result.effect is None


def test_report_requires_confirmation_then_proposes_effect():
    result = turn(Conversation(), "I lost a purple wallet yesterday near the cinema")
    assert result.conversation.state == "confirming"
    assert result.conversation.proposal == "lost_report"
    assert result.effect is None
    confirmed = turn(result.conversation, "yes")
    assert confirmed.effect.kind == "lost_report"


def test_claim_requires_identifying_fact_and_final_confirmation():
    result = turn(Conversation(), "black backpack with two compartments food court yesterday")
    identified = turn(result.conversation, "There is a yellow duck keychain")
    assert identified.conversation.state == "confirming"
    assert identified.conversation.proposal == "claim"
    assert identified.effect is None
    confirmed = turn(identified.conversation, "yes please")
    assert confirmed.effect.kind == "claim"
    assert confirmed.effect.item_id == "one"


def test_yes_with_correction_cannot_submit_old_proposal():
    state = Conversation(
        state="confirming",
        fields=Fields(category="bag", colour="black"),
        proposal="claim",
        selection="one",
    )
    result = turn(state, "yes but actually it was red")
    assert result.effect is None
    assert result.conversation.fields.colour == "red"
    assert result.conversation.proposal != "claim"
    assert result.conversation.selection != "one"


def test_candidate_preference_is_not_proof():
    result = turn(Conversation(), "black backpack with two compartments food court yesterday")
    preference = turn(result.conversation, "the first one")
    assert preference.effect is None
    assert preference.conversation.proposal != "claim"


def test_identifying_colour_does_not_change_item_colour():
    result = turn(Conversation(), "black backpack with two compartments food court yesterday")
    result = turn(result.conversation, "a blue notebook inside")
    assert result.conversation.fields.colour == "black"
    assert result.conversation.proposal == "claim"


def test_identification_attempts_are_bounded():
    result = turn(Conversation(), "black backpack with two compartments food court yesterday")
    for _ in range(2):
        result = turn(result.conversation, "I don't know")
    assert result.conversation.proposal == "lost_report"


def test_completed_confirmation_repeats_receipt_without_effect():
    state = Conversation(
        state="completed",
        receipt=Receipt(reference="LF-DEMO", kind="claim", status="pending_review"),
    )
    result = turn(state, "yes")
    assert "LF-DEMO" in result.reply
    assert result.effect is None


def test_restart_asks_before_discarding_details():
    state = Conversation(fields=Fields(category="bag"))
    result = turn(state, "restart")
    assert result.conversation.restart_pending
    result = turn(result.conversation, "yes")
    assert result.conversation.fields.category is None
    assert result.effect is None


def test_repeat_and_help_do_not_change_fields():
    state = Conversation(fields=Fields(category="bag"), asked="colour")
    assert "colour" in turn(state, "repeat").reply
    assert turn(state, "help").conversation.fields == state.fields


def test_unknown_answers_eventually_offer_report():
    result = turn(Conversation(), "a bag")
    for _ in range(8):
        result = turn(result.conversation, "I don't know")
    assert result.conversation.proposal == "lost_report"


def test_uncertainty_is_not_erased_by_an_unrelated_answer():
    state = Conversation(
        fields=Fields(category="bag", colour="blue", uncertain=["colour"]), asked="lost_date"
    )
    result = turn(state, "yesterday")
    assert "colour" in result.conversation.fields.uncertain
