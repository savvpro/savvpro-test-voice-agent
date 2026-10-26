"""Intent detector — weighted keyword + regex scoring with state-aware priority.

No external AI, no stemming library.  All detection is explicit pattern
matching against the tables in ``constants.py``.

Algorithm:
1. For each intent, find all keyword and regex hits (whole-word matching).
2. Score = best single-hit weight + EXTRA_HIT_BONUS × (total_hits − 1),
   capped at 1.0.
3. Apply state-aware priority: in CONFIRM states, evaluate affirm/deny/
   change_of_mind first — if any scores above threshold, return immediately.
4. Apply disambiguation rules before final scoring.
5. Return argmax(score); if score < CONFIDENCE_THRESHOLD → "unknown".
6. Track runner-up; if gap < AMBIGUITY_MARGIN, record in result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.brain.constants import (
    AMBIGUITY_MARGIN,
    CONFIDENCE_THRESHOLD,
    DISAMBIG_CANCEL_THAT,
    DISAMBIG_NO_WAIT,
    EXTRA_HIT_BONUS,
    INTENT_KEYWORDS,
    INTENT_REGEX_PATTERNS,
    STATE_INTENT_PRIORITY,
)


@dataclass(frozen=True, slots=True)
class IntentResult:
    """Output of :func:`detect_intent`."""

    intent: str
    confidence: float
    runner_up: str | None = None
    runner_up_confidence: float | None = None


def _score_intent(intent: str, text: str) -> float:
    """Score a single intent against *text*.

    Returns a float in [0.0, 1.0].
    """
    hits: list[float] = []

    # Keyword hits (whole-word matching via \b boundaries).
    for phrase, weight in INTENT_KEYWORDS.get(intent, []):
        pattern = r"\b" + re.escape(phrase) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            hits.append(weight)

    # Regex pattern hits.
    for compiled_pattern, weight in INTENT_REGEX_PATTERNS.get(intent, []):
        if compiled_pattern.search(text):
            hits.append(weight)

    if not hits:
        return 0.0

    # Score = best hit weight + bonus per additional hit.
    hits.sort(reverse=True)
    score = hits[0] + EXTRA_HIT_BONUS * (len(hits) - 1)
    return min(score, 1.0)


def _apply_disambiguation(text: str) -> IntentResult | None:
    """Check disambiguation rules; return a forced result or None.

    Rules (applied to text BEFORE general scoring):
    - "no wait" / "wait no" → change_of_mind
    - "cancel that" → deny
    """
    if DISAMBIG_NO_WAIT.search(text):
        score = _score_intent("change_of_mind", text)
        # Ensure at least threshold confidence.
        score = max(score, CONFIDENCE_THRESHOLD + 0.1)
        return IntentResult(intent="change_of_mind", confidence=min(score, 1.0))

    if DISAMBIG_CANCEL_THAT.search(text):
        score = _score_intent("deny", text)
        score = max(score, CONFIDENCE_THRESHOLD + 0.1)
        return IntentResult(intent="deny", confidence=min(score, 1.0))

    return None


def detect_intent(
    intent_text: str,
    state: str | None = None,
) -> IntentResult:
    """Detect the caller's intent from normalised text.

    Args:
        intent_text: The ``intent_text`` output from the normalizer.
        state: The current dialogue state name (e.g. ``"CONFIRM_SLOT"``).
            Used for state-aware priority.

    Returns:
        An ``IntentResult`` with the detected intent, confidence, and
        optional runner-up information.
    """
    # Step 1: Apply disambiguation rules first.
    disambig = _apply_disambiguation(intent_text)
    if disambig is not None:
        return disambig

    # Step 2: State-aware priority — check priority intents first.
    if state and state in STATE_INTENT_PRIORITY:
        priority_intents = STATE_INTENT_PRIORITY[state]
        for intent in priority_intents:
            score = _score_intent(intent, intent_text)
            if score >= CONFIDENCE_THRESHOLD:
                return IntentResult(intent=intent, confidence=score)

    # Step 3: Score all intents.
    all_intents = list(INTENT_KEYWORDS.keys())
    scores: list[tuple[str, float]] = [
        (intent, _score_intent(intent, intent_text))
        for intent in all_intents
    ]

    # Sort by score descending.
    scores.sort(key=lambda x: x[1], reverse=True)

    best_intent, best_score = scores[0]
    runner_up_intent: str | None = None
    runner_up_score: float | None = None

    if len(scores) > 1:
        runner_up_intent, runner_up_score = scores[1]

    # Step 4: Apply threshold.
    if best_score < CONFIDENCE_THRESHOLD:
        return IntentResult(
            intent="unknown",
            confidence=best_score,
            runner_up=runner_up_intent,
            runner_up_confidence=runner_up_score,
        )

    # Step 5: Check ambiguity margin.
    if (
        runner_up_score is not None
        and best_score - runner_up_score < AMBIGUITY_MARGIN
    ):
        return IntentResult(
            intent=best_intent,
            confidence=best_score,
            runner_up=runner_up_intent,
            runner_up_confidence=runner_up_score,
        )

    return IntentResult(
        intent=best_intent,
        confidence=best_score,
        runner_up=runner_up_intent,
        runner_up_confidence=runner_up_score,
    )
