"""Small, explainable text classifier used for intent confidence and review logs.

Multinomial Naive Bayes over unigrams + bigrams. No external ML dependency, so every
number it returns can be traced back to word counts in data/intent_model.json.

What changed vs. v1 (see DESIGN.md "classifier" section):
  * amounts ("500", "five hundred", "$12.50") collapse to one <num> token, so
    "spent 500 on lunch" and "spent 12 on lunch" look identical (v1 ignored numbers);
  * bigrams capture order-ish cues ("spend <num>" = log, "total spend" = query);
  * uniform priors: template-generated intents are huge, and v1's class prior pulled
    generic phrases toward the biggest class;
  * confidence = softmax(score / temperature) * (1 - oov_ratio): words the model never
    saw lower confidence instead of being silently skipped;
  * the model file is cached and only re-read when it changes on disk.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from difflib import get_close_matches
from pathlib import Path
from typing import Any

MODEL_VERSION = 2
TOKEN_PATTERN = re.compile(r"[a-z]+|\d+(?:[.,]\d+)*")
NUM = "<num>"
NUMBER_WORDS = {
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
    "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    "hundred", "thousand", "k",
}
SYNONYMS = {
    "spending": "spend", "spent": "spend", "spendings": "spend", "expenses": "expense",
    "expenditure": "expense", "expenditures": "expense", "costs": "cost", "paid": "spend",
    "payment": "spend", "payments": "spend", "bought": "spend", "purchased": "spend",
    "mt": "my", "whats": "what",
}
FUZZY_CANONICAL = tuple({
    *SYNONYMS, *SYNONYMS.values(), "today", "yesterday", "tomorrow", "total", "expense",
    "spend", "money", "delete", "remove", "update", "change", "summary", "groceries",
})
INTENT_ALIASES = {"spending_summary": "query_total", "today_report": "query_total", "spending_breakdown": "query_total"}
MODEL_PATH = Path(__file__).resolve().parents[1] / "data" / "intent_model.json"
UNKNOWN = "unknown"


def tokenize(text: str) -> list[str]:
    """Lowercase, canonicalise synonyms, fix typos, collapse amounts to <num>."""
    tokens: list[str] = []
    for raw in TOKEN_PATTERN.findall(text.lower()):
        if raw[0].isdigit() or raw in NUMBER_WORDS:
            if not tokens or tokens[-1] != NUM:      # "five hundred" -> one <num>
                tokens.append(NUM)
            continue
        canonical = SYNONYMS.get(raw, raw)
        if canonical == raw and len(raw) >= 4:
            close = get_close_matches(raw, FUZZY_CANONICAL, n=1, cutoff=0.82)
            if close:
                canonical = SYNONYMS.get(close[0], close[0])
        tokens.append(canonical)
    return tokens


def features(text: str) -> tuple[list[str], list[str]]:
    """(unigrams, unigrams + bigrams)."""
    unigrams = tokenize(text)
    bigrams = [f"{a}_{b}" for a, b in zip(unigrams, unigrams[1:])]
    return unigrams, unigrams + bigrams


def canonical_label(label: str) -> str:
    return INTENT_ALIASES.get(label, label)


def train_model(samples: list[dict[str, str]], temperature: float = 1.0) -> dict[str, Any]:
    labelled = [(sample["text"], canonical_label(sample["intent"])) for sample in samples]
    labels = sorted({label for _, label in labelled})
    token_counts: dict[str, Counter[str]] = {label: Counter() for label in labels}
    label_counts: Counter[str] = Counter()
    for text, label in labelled:
        label_counts[label] += 1
        token_counts[label].update(features(text)[1])
    vocabulary = sorted({token for counts in token_counts.values() for token in counts})
    return {
        "version": MODEL_VERSION,
        "labels": labels,
        "vocabulary": vocabulary,
        "label_counts": dict(label_counts),
        "token_counts": {label: dict(counts) for label, counts in token_counts.items()},
        "token_totals": {label: sum(counts.values()) for label, counts in token_counts.items()},
        "sample_count": len(labelled),
        "temperature": temperature,
        "uniform_priors": True,
    }


def predict(model: dict[str, Any], text: str) -> tuple[str, float, list[dict[str, Any]]]:
    unigrams, feats = features(text)
    vocabulary = set(model["vocabulary"])
    known_unigrams = sum(1 for token in unigrams if token in vocabulary)
    if not unigrams or known_unigrams == 0:
        return UNKNOWN, 0.0, []
    oov_ratio = 1 - known_unigrams / len(unigrams)
    known = [token for token in feats if token in vocabulary]
    temperature = max(float(model.get("temperature", 1.0)), 1e-6)
    vocabulary_size = len(vocabulary)
    scores: list[tuple[str, float]] = []
    for label in model["labels"]:
        counts = model["token_counts"][label]
        token_total = model.get("token_totals", {}).get(label) or sum(counts.values())
        score = 0.0 if model.get("uniform_priors", True) else math.log(model["label_counts"][label] / model["sample_count"])
        for token in known:
            score += math.log((counts.get(token, 0) + 1) / (token_total + vocabulary_size))
        scores.append((label, score / temperature))
    scores.sort(key=lambda item: item[1], reverse=True)
    top = scores[0][1]
    weights = [(label, math.exp(score - top)) for label, score in scores]
    denominator = sum(weight for _, weight in weights)
    ranked = [{"intent": label, "confidence": round(weight / denominator, 4)} for label, weight in weights[:3]]
    ranked[0]["oov_ratio"] = round(oov_ratio, 3)
    confidence = round(ranked[0]["confidence"] * (1 - oov_ratio), 4)
    return ranked[0]["intent"], confidence, ranked


_CACHE: dict[str, Any] = {"mtime": None, "model": None}


def load_model() -> dict[str, Any] | None:
    """Read the model file, re-reading only when it changed. Old (v1) models are rejected."""
    try:
        mtime = MODEL_PATH.stat().st_mtime_ns
    except FileNotFoundError:
        return None
    if _CACHE["mtime"] != mtime or _CACHE["model"] is None:
        try:
            model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if model.get("version") != MODEL_VERSION:
            return None                          # needs `python train.py`
        _CACHE.update(mtime=mtime, model=model)
    return _CACHE["model"]


def classify(text: str) -> tuple[str, float, list[dict[str, Any]]]:
    model = load_model()
    if model is None:
        return "untrained", 0.0, []
    return predict(model, text)