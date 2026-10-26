"""Train Penny's small intent classifier from JSON data and reviewer corrections.

    python train.py

Reports accuracy on HELD-OUT data (never trained on during evaluation), then retrains on
everything and writes data/intent_model.json + data/eval_report.json.

Held-out rules (so the number means "handles phrasings it has not seen"):
  * hand-written `examples`: every 4th one is withheld;
  * `templates`: every 4th *opener* is withheld, so test sentences use openers the model
    never saw (sharing subjects/periods is deliberate: it tests phrasing, not vocabulary).
Reviewer corrections always go to training (x CORRECTION_WEIGHT), never to the test set.
"""

from __future__ import annotations

import json
from collections import defaultdict
from itertools import product
from pathlib import Path

from app.intent_model import MODEL_PATH, canonical_label, predict, train_model

ROOT = Path(__file__).resolve().parent
INTENTS_PATH = ROOT / "config" / "intents.json"
CORRECTIONS_PATH = ROOT / "data" / "corrections.jsonl"
REPORT_PATH = ROOT / "data" / "eval_report.json"
TEMPLATE_CAP = 60          # max generated sentences per intent, so templates can't swamp hand-written data
CORRECTION_WEIGHT = 3      # a human fixed this one: count it more than a generated sentence
TEMPERATURES = (1, 2, 3, 4, 6, 8, 12, 16, 24)
CONFIDENT = 0.75           # keep in sync with the gate in app/main.py


def spread(items: list[str], limit: int) -> list[str]:
    """Deterministic, evenly spaced subset (not just the first N, which would be one opener)."""
    if len(items) <= limit:
        return items
    step = len(items) / limit
    return [items[int(i * step)] for i in range(limit)]


def split_config(config: dict) -> tuple[list[dict], list[dict]]:
    train: list[dict] = []
    test: list[dict] = []
    for intent in config["intents"]:
        label = canonical_label(intent["name"])
        for index, text in enumerate(intent.get("examples", [])):
            (test if index % 4 == 3 else train).append({"text": text, "intent": label})
        template = intent.get("templates")
        if template:
            kept = [o for i, o in enumerate(template["openers"]) if i % 4 != 3]
            held = [o for i, o in enumerate(template["openers"]) if i % 4 == 3]
            def expand(openers: list[str]) -> list[str]:
                return [" ".join(parts).strip() for parts in product(openers, template["subjects"], template["periods"])]
            train += [{"text": t, "intent": label} for t in spread(expand(kept), TEMPLATE_CAP)]
            test += [{"text": t, "intent": label} for t in spread(expand(held), TEMPLATE_CAP // 3)] if held else []
    return train, test


def load_corrections() -> tuple[list[dict], int]:
    samples: list[dict] = []
    skipped = 0
    if CORRECTIONS_PATH.exists():
        for line in CORRECTIONS_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                text, intent = str(item["text"]).strip(), canonical_label(str(item["intent"]).strip())
            except (json.JSONDecodeError, KeyError):
                skipped += 1
                continue
            if text and intent:
                samples += [{"text": text, "intent": intent}] * CORRECTION_WEIGHT
            else:
                skipped += 1
    return samples, skipped


def evaluate(model: dict, test: list[dict]) -> dict:
    labels = model["labels"]
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    rows = []
    for sample in test:
        predicted, confidence, _ = predict(model, sample["text"])
        matrix[sample["intent"]][predicted] += 1
        rows.append((sample["text"], sample["intent"], predicted, confidence))
    correct = [r for r in rows if r[1] == r[2]]
    per_class = {}
    for label in labels:
        tp = matrix[label].get(label, 0)
        actual = sum(matrix[label].values())
        predicted_n = sum(matrix[a].get(label, 0) for a in labels)
        precision = tp / predicted_n if predicted_n else 0.0
        recall = tp / actual if actual else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"support": actual, "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}
    confident = [r for r in rows if r[3] >= CONFIDENT]
    return {
        "test_samples": len(rows),
        "accuracy": round(len(correct) / len(rows), 3) if rows else 0.0,
        "per_class": per_class,
        "confusion": {a: dict(p) for a, p in matrix.items()},
        "mean_confidence_correct": round(sum(r[3] for r in correct) / len(correct), 3) if correct else 0.0,
        "mean_confidence_wrong": round(sum(r[3] for r in rows if r[1] != r[2]) / max(1, len(rows) - len(correct)), 3),
        "confident_share": round(len(confident) / len(rows), 3) if rows else 0.0,
        "accuracy_when_confident": round(sum(r[1] == r[2] for r in confident) / len(confident), 3) if confident else 0.0,
        "misses": [{"text": t, "expected": e, "got": p, "confidence": c} for t, e, p, c in rows if e != p][:25],
        "brier": round(sum((c - (e == p)) ** 2 for _, e, p, c in rows) / len(rows), 4) if rows else 1.0,
    }


def tune_temperature(train: list[dict], test: list[dict]) -> float:
    """Pick the temperature whose confidences best match correctness (lowest Brier score).
    Temperature never changes which intent wins, so accuracy stays an unbiased held-out number."""
    best = min(TEMPERATURES, key=lambda t: evaluate(train_model(train, float(t)), test)["brier"])
    return float(best)


def print_report(report: dict, temperature: float) -> None:
    print(f"held-out samples: {report['test_samples']}   accuracy: {report['accuracy']:.3f}   temperature: {temperature:g}")
    print(f"confidence: mean when right {report['mean_confidence_correct']:.2f}, when wrong {report['mean_confidence_wrong']:.2f}; "
          f"{report['confident_share']:.0%} of turns reach >= {CONFIDENT} and are {report['accuracy_when_confident']:.1%} correct")
    print("\nper-intent (held-out):\nintent | support | precision | recall | f1")
    for label, m in report["per_class"].items():
        print(f"{label} | {m['support']} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f}")
    labels = list(report["per_class"])
    print("\nconfusion matrix (actual rows, predicted columns):")
    print("actual\\predicted | " + " | ".join(labels + ["unknown"]))
    for actual in labels:
        row = report["confusion"].get(actual, {})
        print(actual + " | " + " | ".join(str(row.get(p, 0)) for p in labels + ["unknown"]))
    if report["misses"]:
        print("\nmisses:")
        for miss in report["misses"]:
            print(f"  {miss['text']!r}: expected {miss['expected']}, got {miss['got']} ({miss['confidence']:.2f})")


def main() -> None:
    config = json.loads(INTENTS_PATH.read_text(encoding="utf-8"))
    train, test = split_config(config)
    corrections, skipped = load_corrections()
    train += corrections
    labels = {s["intent"] for s in train}
    if not labels & {"out_of_scope", "fallback"}:
        print("WARNING: no out_of_scope/fallback intent in config. Off-topic input (weather, jokes) will be forced into an expense intent.")
    if skipped:
        print(f"skipped {skipped} malformed correction line(s)")
    untested = sorted(labels - {s["intent"] for s in test})
    if untested:
        print(f"WARNING: no held-out examples for {untested}; add >= 4 examples or a template to measure them.")

    temperature = tune_temperature(train, test)
    report = evaluate(train_model(train, temperature), test)
    print_report(report, temperature)

    final = train_model(train + test, temperature)      # ship a model that has seen all the data
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(json.dumps(final), encoding="utf-8")
    REPORT_PATH.write_text(json.dumps({**report, "temperature": temperature, "train_samples": len(train), "corrections_used": len(corrections) // CORRECTION_WEIGHT}, indent=2), encoding="utf-8")
    print(f"\nwrote {MODEL_PATH} ({final['sample_count']} samples) and {REPORT_PATH}")


if __name__ == "__main__":
    main()