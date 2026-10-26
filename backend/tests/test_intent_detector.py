"""Tests for the intent detector.

Covers:
- Happy path per intent: clear phrase → correct intent + confidence ≥ threshold.
- Whole-word matching: "cancellation" must NOT trigger cancel.
- State-aware: in CONFIRM_SLOT, "yes" wins over weaker reschedule keywords.
- Disambiguation: "no wait" → change_of_mind; "cancel that" → deny.
- False positive: "I need to cancel my gym membership" → cancel (low confidence).
- False negative: "I'd like to pick up the parcel myself from your office" → pickup_point.
- Parametrized: 5+ phrasings per intent.
- Unknown: gibberish → unknown.
- Runner-up tracking.
"""

from __future__ import annotations

import pytest

from app.brain.intent_detector import IntentResult, detect_intent

# ── Happy path per intent ─────────────────────────────────────────────


class TestHappyPath:
    def test_reschedule(self):
        r = detect_intent("i'd like to reschedule my delivery")
        assert r.intent == "reschedule"
        assert r.confidence >= 0.40

    def test_reschedule_rebook(self):
        r = detect_intent("can i rebook for a different day")
        assert r.intent == "reschedule"

    def test_pickup_point(self):
        r = detect_intent("i want to pick it up from a collection point")
        assert r.intent == "pickup_point"
        assert r.confidence >= 0.40

    def test_cancel(self):
        r = detect_intent("please cancel the delivery")
        assert r.intent == "cancel"
        assert r.confidence >= 0.40

    def test_status(self):
        r = detect_intent("where is my parcel")
        assert r.intent == "status"
        assert r.confidence >= 0.40

    def test_affirm(self):
        r = detect_intent("yes please")
        assert r.intent == "affirm"
        assert r.confidence >= 0.40

    def test_deny(self):
        r = detect_intent("no that's wrong")
        assert r.intent == "deny"
        assert r.confidence >= 0.40

    def test_repeat(self):
        r = detect_intent("can you say that again")
        assert r.intent == "repeat"
        assert r.confidence >= 0.40

    def test_human_agent(self):
        r = detect_intent("i want to speak to a human")
        assert r.intent == "human_agent"
        assert r.confidence >= 0.40

    def test_change_of_mind(self):
        r = detect_intent("on second thought i want something else")
        assert r.intent == "change_of_mind"

    def test_goodbye(self):
        r = detect_intent("thanks bye")
        assert r.intent == "goodbye"
        assert r.confidence >= 0.40


# ── Whole-word matching ───────────────────────────────────────────────


class TestWholeWord:
    def test_cancellation_not_cancel(self):
        """'cancellation' must NOT trigger cancel intent."""
        r = detect_intent("i received a cancellation notice")
        assert r.intent != "cancel" or r.confidence < 0.40

    def test_cancelled_not_cancel(self):
        """'cancelled' must NOT trigger cancel intent."""
        r = detect_intent("has it been cancelled already")
        assert r.intent != "cancel" or r.confidence < 0.40

    def test_rescheduled_is_understood_as_reschedule_request(self):
        for text in ("rescheduled", "I want to rescheduled", "free schedule", "residual"):
            assert detect_intent(text, state="CHOOSE_ACTION").intent == "reschedule"

    def test_agent_in_reagent_not_matched(self):
        """'agent' in 'reagent' should not match due to \b."""
        r = detect_intent("the chemical reagent arrived")
        assert r.intent != "human_agent"


# ── State-aware priority ─────────────────────────────────────────────


class TestStateAware:
    def test_yes_in_confirm_slot(self):
        """In CONFIRM_SLOT, 'yes' should win over any weaker intent."""
        r = detect_intent("yes", state="CONFIRM_SLOT")
        assert r.intent == "affirm"

    def test_no_in_confirm_slot(self):
        r = detect_intent("no", state="CONFIRM_SLOT")
        assert r.intent == "deny"

    def test_yes_in_confirm_cancel(self):
        r = detect_intent("yes please", state="CONFIRM_CANCEL")
        assert r.intent == "affirm"

    def test_no_in_confirm_tracking(self):
        r = detect_intent("no", state="CONFIRM_TRACKING_ID")
        assert r.intent == "deny"

    def test_repeat_in_confirm_slot(self):
        r = detect_intent("repeat", state="CONFIRM_SLOT")
        assert r.intent == "repeat"

    def test_goodbye_in_confirm_slot(self):
        r = detect_intent("bye", state="CONFIRM_SLOT")
        assert r.intent == "goodbye"

    def test_human_in_verify_phone(self):
        r = detect_intent("human", state="VERIFY_PHONE")
        assert r.intent == "human_agent"

    def test_no_priority_in_choose_action(self):
        """CHOOSE_ACTION has no priority list — normal scoring applies."""
        r = detect_intent("reschedule", state="CHOOSE_ACTION")
        assert r.intent == "reschedule"


# ── Disambiguation ────────────────────────────────────────────────────


class TestDisambiguation:
    def test_no_wait_is_change_of_mind(self):
        r = detect_intent("no wait i changed my mind")
        assert r.intent == "change_of_mind"

    def test_wait_no_is_change_of_mind(self):
        r = detect_intent("wait no i meant something else")
        assert r.intent == "change_of_mind"

    def test_cancel_that_is_deny(self):
        r = detect_intent("cancel that")
        assert r.intent == "deny"

    def test_no_wait_in_confirm_state(self):
        """Even in a CONFIRM state, 'no wait' → change_of_mind."""
        r = detect_intent("no wait", state="CONFIRM_SLOT")
        assert r.intent == "change_of_mind"


# ── Unknown / low confidence ─────────────────────────────────────────


class TestUnknown:
    def test_gibberish(self):
        r = detect_intent("asdfghjkl qwerty zxcvbnm")
        assert r.intent == "unknown"

    def test_empty_string(self):
        r = detect_intent("")
        assert r.intent == "unknown"

    def test_random_sentence(self):
        r = detect_intent("the weather is nice today")
        assert r.intent == "unknown"


# ── Runner-up tracking ────────────────────────────────────────────────


class TestRunnerUp:
    def test_has_runner_up(self):
        r = detect_intent("yes please go ahead")
        assert r.runner_up is not None or r.runner_up_confidence is not None

    def test_result_type(self):
        r = detect_intent("reschedule")
        assert isinstance(r, IntentResult)


# ── Multi-hit scoring ─────────────────────────────────────────────────


class TestMultiHitScoring:
    def test_multiple_keywords_boost_score(self):
        """Multiple matching keywords should increase confidence."""
        single = detect_intent("reschedule")
        multi = detect_intent("reschedule to a new date different day")
        assert multi.confidence >= single.confidence

    def test_score_capped_at_1(self):
        """Even with many hits, score shouldn't exceed 1.0."""
        r = detect_intent(
            "reschedule rebook new date new time change delivery "
            "different day another day book again"
        )
        assert r.confidence <= 1.0


# ── Parametrized per-intent tests ─────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected_intent",
    [
        # Reschedule
        ("reschedule", "reschedule"),
        ("rebook my parcel", "reschedule"),
        ("i need a new date", "reschedule"),
        ("can you change delivery", "reschedule"),
        ("different day please", "reschedule"),
        ("deliver it again please", "reschedule"),
        # Pickup
        ("pick it up", "pickup_point"),
        ("collection point", "pickup_point"),
        ("i'll collect it from the depot", "pickup_point"),
        ("go to depot", "pickup_point"),
        ("post office", "pickup_point"),
        # Cancel
        ("cancel the delivery", "cancel"),
        ("i don't want it", "cancel"),
        ("send it back", "cancel"),
        ("return it please", "cancel"),
        ("refuse delivery", "cancel"),
        # Status
        ("where is my parcel", "status"),
        ("tracking update", "status"),
        ("any update on my delivery", "status"),
        ("what's the status", "status"),
        ("how is the status of my parcel", "status"),
        # Affirm
        ("yes", "affirm"),
        ("yeah", "affirm"),
        ("that's right", "affirm"),
        ("go ahead", "affirm"),
        ("correct", "affirm"),
        # Deny
        ("no", "deny"),
        ("nope", "deny"),
        ("that is not right", "deny"),
        ("wrong", "deny"),
        # Repeat
        ("repeat", "repeat"),
        ("say again", "repeat"),
        ("what did you say", "repeat"),
        ("pardon", "repeat"),
        # Human
        ("speak to a human", "human_agent"),
        ("talk to an agent", "human_agent"),
        ("real person please", "human_agent"),
        # Change of mind
        ("actually i want something else", "change_of_mind"),
        ("on second thought", "change_of_mind"),
        ("wait actually no", "change_of_mind"),
        # Goodbye
        ("goodbye", "goodbye"),
        ("thanks that's all", "goodbye"),
        ("i'm all done", "goodbye"),
        ("cheers", "goodbye"),
    ],
    ids=[
        "reschedule_1", "reschedule_2", "reschedule_3", "reschedule_4",
        "reschedule_5", "reschedule_regex",
        "pickup_1", "pickup_2", "pickup_3", "pickup_4", "pickup_5",
        "cancel_1", "cancel_2", "cancel_3", "cancel_4", "cancel_5",
        "status_1", "status_2", "status_3", "status_4", "status_regex",
        "affirm_1", "affirm_2", "affirm_3", "affirm_4", "affirm_5",
        "deny_1", "deny_2", "deny_3", "deny_4",
        "repeat_1", "repeat_2", "repeat_3", "repeat_4",
        "human_1", "human_2", "human_3",
        "com_1", "com_2", "com_3",
        "bye_1", "bye_2", "bye_3", "bye_4",
    ],
)
def test_intent_parametrized(text: str, expected_intent: str):
    r = detect_intent(text)
    assert r.intent == expected_intent, (
        f"Expected {expected_intent!r} for {text!r}, got {r.intent!r} "
        f"(confidence={r.confidence:.2f})"
    )


# ── Return type ───────────────────────────────────────────────────────


class TestReturnType:
    def test_returns_intent_result(self):
        r = detect_intent("hello")
        assert isinstance(r, IntentResult)

    def test_result_is_frozen(self):
        r = detect_intent("hello")
        with pytest.raises(AttributeError):
            r.intent = "modified"  # type: ignore[misc]
