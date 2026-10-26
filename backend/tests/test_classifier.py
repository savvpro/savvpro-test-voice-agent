import json
from pathlib import Path

from app.intent_model import predict, train_model


def _samples():
    config_path = Path(__file__).parents[1] / "config" / "intents.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    return [{"text": example, "intent": intent["name"]} for intent in config["intents"] for example in intent["examples"]]


def test_intent_training_regression_accuracy():
    samples = _samples()
    model = train_model(samples)
    aliases = {"spending_summary": "query_total", "today_report": "query_total", "spending_breakdown": "query_total"}
    correct = sum(predict(model, sample["text"])[0] == aliases.get(sample["intent"], sample["intent"]) for sample in samples)
    accuracy = correct / len(samples)
    assert accuracy >= 0.85


def test_trained_model_returns_traceable_ranked_predictions():
    model = train_model(_samples())
    intent, confidence, ranked = predict(model, "What did I spend money on today?")
    assert intent == "query_total"
    assert 0 <= confidence <= 1
    assert ranked[0]["intent"] == intent


def test_classifier_normalizes_spending_synonyms_and_typos():
    model = train_model(_samples())
    intent, _, _ = predict(model, "what is my total spnding")
    assert intent == "query_total"