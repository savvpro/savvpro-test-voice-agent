"""Loads the YAML vocabulary in nlu/data once per process."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(__file__).parent / "data"
LEXICON_PATH = DATA_DIR / "lexicon.yaml"
INTENTS_PATH = DATA_DIR / "intents.yaml"


@lru_cache
def load_lexicon() -> dict[str, Any]:
    with LEXICON_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_intents(path: Path = INTENTS_PATH) -> dict[str, list[str]]:
    """Training utterances by intent.

    Every utterance must load as a string: YAML turns bare `yes`/`no` into
    booleans and `03001234567` into an octal integer, so those must be quoted.
    """
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for intent, utterances in data.items():
        bad = [u for u in utterances if not isinstance(u, str)]
        if bad:
            raise ValueError(f"{path.name}: quote these {intent} utterances: {bad}")
    return data
