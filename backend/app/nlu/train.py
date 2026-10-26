"""Train the intent classifier: ``python -m app.nlu.train``.

Utterances from intents.yaml are normalized and entity values replaced by
placeholders exactly as at runtime (classifier.to_features), then fed to
TF-IDF (word 1-2 grams + char_wb 2-4 grams) -> LogisticRegression. Char
n-grams make the model robust to STT misspellings ("apointment", "cancle").

Prints classification reports for a held-out split and for 5-fold
cross-validation, saves the model trained on *all* data, and writes
reports/nlu_metrics.json.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

from app.config import get_settings
from app.nlu.classifier import to_features
from app.nlu.lexicon import INTENTS_PATH, load_intents
from app.nlu.normalizer import normalize

RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 5
# Higher C than the default 1.0: with 20 classes the default spreads probability
# so thinly that even clear utterances rarely pass the 0.60 fusion threshold.
REGULARIZATION_C = 10.0


def build_pipeline() -> Pipeline:
    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    analyzer="word", ngram_range=(1, 2), token_pattern=r"[^\s]+", sublinear_tf=True
                ),
            ),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)),
        ]
    )
    classifier = LogisticRegression(
        max_iter=2000, class_weight="balanced", C=REGULARIZATION_C, random_state=RANDOM_STATE
    )
    return Pipeline([("features", features), ("clf", classifier)])


def load_dataset(path: Path = INTENTS_PATH) -> tuple[list[str], list[str]]:
    texts, labels = [], []
    for intent, utterances in load_intents(path).items():
        for utterance in utterances:
            texts.append(to_features(normalize(utterance)))
            labels.append(intent)
    return texts, labels


def _per_intent(y_true: list[str], y_pred: list[str]) -> dict[str, dict[str, float]]:
    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    return {
        label: {k: round(float(v), 4) for k, v in scores.items()}
        for label, scores in report.items()
        if isinstance(scores, dict) and label not in ("macro avg", "weighted avg")
    }


def evaluate(texts: list[str], labels: list[str]) -> dict:
    """Score the model on data it was not trained on. Does not touch the saved model.

    Two views: one stratified 80/20 split, and 5-fold cross-validation where every
    utterance is predicted exactly once by a model that never saw it. The CV view
    covers all utterances, so its per-intent scores are far less noisy than the
    split's (which has only ~10 test examples per intent).
    """
    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=TEST_SIZE, stratify=labels, random_state=RANDOM_STATE
    )
    test_predicted = list(build_pipeline().fit(x_train, y_train).predict(x_test))

    folds = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    cv_predicted = [""] * len(texts)
    fold_accuracy = []
    for train_idx, test_idx in folds.split(texts, labels):
        model = build_pipeline().fit([texts[i] for i in train_idx], [labels[i] for i in train_idx])
        predicted = model.predict([texts[i] for i in test_idx])
        for i, p in zip(test_idx, predicted, strict=True):
            cv_predicted[i] = p
        fold_accuracy.append(accuracy_score([labels[i] for i in test_idx], predicted))

    return {
        "test_accuracy": round(float(accuracy_score(y_test, test_predicted)), 4),
        "test_macro_f1": round(float(f1_score(y_test, test_predicted, average="macro")), 4),
        "cv_accuracy_mean": round(float(np.mean(fold_accuracy)), 4),
        "cv_accuracy_std": round(float(np.std(fold_accuracy)), 4),
        "cv_macro_f1": round(float(f1_score(labels, cv_predicted, average="macro")), 4),
        "test_per_intent": _per_intent(y_test, test_predicted),
        "cv_per_intent": _per_intent(labels, cv_predicted),
        "test_report_text": classification_report(
            y_test, test_predicted, digits=3, zero_division=0
        ),
        "cv_report_text": classification_report(labels, cv_predicted, digits=3, zero_division=0),
    }


def _compact(model: Pipeline) -> Pipeline:
    """Store weights as float32: halves the file, predictions are unaffected."""
    clf = model.named_steps["clf"]
    clf.coef_ = clf.coef_.astype(np.float32)
    clf.intercept_ = clf.intercept_.astype(np.float32)
    return model


def fit_and_save(model_path: Path) -> None:
    """Train on all data and save. No evaluation, no report: used for auto-training."""
    texts, labels = load_dataset()
    model = _compact(build_pipeline().fit(texts, labels))
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path, compress=3)


def train(
    model_path: Path | None = None,
    reports_dir: Path | None = None,
    verbose: bool = True,
) -> dict:
    """Evaluate, then train on all data, save the model and write the metrics report."""
    settings = get_settings()
    model_path = model_path or settings.nlu_model_path
    reports_dir = reports_dir or settings.reports_dir

    texts, labels = load_dataset()
    metrics = evaluate(texts, labels)
    fit_and_save(model_path)

    summary = {
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "n_samples": len(texts),
        "n_intents": len(set(labels)),
        "test_size": TEST_SIZE,
        "cv_folds": CV_FOLDS,
        "model_bytes": model_path.stat().st_size,
        **{k: v for k, v in metrics.items() if not k.endswith("report_text")},
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "nlu_metrics.json").write_text(json.dumps(summary, indent=2) + "\n")

    if verbose:
        print(f"{len(texts)} utterances, {summary['n_intents']} intents\n")
        print(f"== held-out {int(TEST_SIZE * 100)}% split ==")
        print(metrics["test_report_text"])
        print(f"== {CV_FOLDS}-fold cross-validation (every utterance predicted once) ==")
        print(metrics["cv_report_text"])
        print(
            f"held-out accuracy {summary['test_accuracy']:.3f} | "
            f"{CV_FOLDS}-fold CV accuracy {summary['cv_accuracy_mean']:.3f} "
            f"± {summary['cv_accuracy_std']:.3f}"
        )
        print(f"model -> {model_path} ({summary['model_bytes'] / 1024:.0f} KB)")
    return summary


if __name__ == "__main__":
    train()
