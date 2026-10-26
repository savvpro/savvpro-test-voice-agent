"""Loads the trained intent model lazily and returns ranked predictions."""

import logging
import threading
from functools import lru_cache
from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline

from app.config import get_settings
from app.nlu.entities import delexicalize

logger = logging.getLogger(__name__)


def to_features(normalized_text: str) -> str:
    """The exact text the model sees, at training and at prediction time."""
    return delexicalize(normalized_text)


class IntentClassifier:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self._model: Pipeline | None = None
        self._lock = threading.Lock()

    def _load(self) -> Pipeline:
        with self._lock:
            if self._model is None:
                if not self.model_path.exists():
                    from app.nlu.train import fit_and_save

                    logger.info("NLU model missing at %s, training it now", self.model_path)
                    fit_and_save(self.model_path)
                self._model = joblib.load(self.model_path)
        return self._model

    def predict(self, normalized_text: str, top_k: int = 3) -> list[tuple[str, float]]:
        """Top-k (intent, probability), most likely first. Empty text -> []."""
        if not normalized_text:
            return []
        model = self._load()
        probabilities = model.predict_proba([to_features(normalized_text)])[0]
        ranked = sorted(zip(model.classes_, probabilities, strict=True), key=lambda p: -p[1])
        return [(str(intent), float(prob)) for intent, prob in ranked[:top_k]]


@lru_cache
def get_classifier() -> IntentClassifier:
    return IntentClassifier(get_settings().nlu_model_path)
