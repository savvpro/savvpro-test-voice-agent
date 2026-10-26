"""Hybrid NLU: rules -> classifier -> fuzzy keywords -> dialogue context.

    rule hit                                   -> rule      (0.95)
    classifier top probability >= 0.60         -> ml
    fuzzy keyword score >= 0.80                -> fuzzy
    dialogue expects a slot and it was found   -> inform    (context)
    otherwise                                  -> nlu_fallback

Entities are always extracted, whatever the intent.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel

from app.nlu.classifier import IntentClassifier, get_classifier
from app.nlu.entities import Entities, extract_entities
from app.nlu.fuzzy import match_intent_keywords
from app.nlu.normalizer import normalize
from app.nlu.rules import match_rules

ML_THRESHOLD = 0.60
FUZZY_THRESHOLD = 0.80
CONTEXT_CONFIDENCE = 0.70
FALLBACK_INTENT = "nlu_fallback"

Source = Literal["rule", "ml", "fuzzy", "context", "fallback"]

# expected_slot -> entity fields that fill it
_SLOT_ENTITIES: dict[str, tuple[str, ...]] = {
    "department": ("department", "unknown_department"),
    "doctor": ("doctor",),
    "date": ("date",),
    "time": ("time", "time_of_day"),
    "patient_name": ("patient_name",),
    "phone": ("phone",),
    "booking_ref": ("booking_ref",),
}


class Alternative(BaseModel):
    intent: str
    confidence: float


class NLUResult(BaseModel):
    text: str
    normalized_text: str
    intent: str
    confidence: float
    source: Source
    entities: Entities
    alternatives: list[Alternative]
    rule_pattern: str | None = None


def _expected_slot_filled(expected_slot: str | None, entities: Entities) -> bool:
    if expected_slot is None:
        return False
    fields = _SLOT_ENTITIES.get(expected_slot, ())
    return any(getattr(entities, f) is not None for f in fields)


def parse(
    text: str,
    expected_slot: str | None = None,
    now: dt.datetime | None = None,
    classifier: IntentClassifier | None = None,
) -> NLUResult:
    normalized = normalize(text)
    entities = extract_entities(normalized, now=now, expected_slot=expected_slot)
    predictions = (classifier or get_classifier()).predict(normalized, top_k=3)
    alternatives = [Alternative(intent=i, confidence=round(p, 4)) for i, p in predictions]

    def result(intent: str, confidence: float, source: Source, pattern: str | None = None):
        return NLUResult(
            text=text,
            normalized_text=normalized,
            intent=intent,
            confidence=round(confidence, 4),
            source=source,
            entities=entities,
            alternatives=alternatives,
            rule_pattern=pattern,
        )

    if not normalized:
        return result(FALLBACK_INTENT, 0.0, "fallback")

    rule = match_rules(normalized)
    if rule:
        return result(rule.intent, rule.confidence, "rule", rule.pattern)

    if predictions and predictions[0][1] >= ML_THRESHOLD:
        return result(predictions[0][0], predictions[0][1], "ml")

    fuzzy = match_intent_keywords(normalized)
    if fuzzy and fuzzy[0][1] >= FUZZY_THRESHOLD:
        return result(fuzzy[0][0], fuzzy[0][1], "fuzzy")

    if _expected_slot_filled(expected_slot, entities):
        return result("inform", CONTEXT_CONFIDENCE, "context")

    top_confidence = predictions[0][1] if predictions else 0.0
    return result(FALLBACK_INTENT, top_confidence, "fallback")
