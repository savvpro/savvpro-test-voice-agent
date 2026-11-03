"""
Script to download Piper voice model files if not already cached.
Usage:
    python scripts/download_piper_model.py
"""

import os
import urllib.request
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

MODEL_PATH = MODEL_DIR / "en_US-lessac-medium.onnx"
CONFIG_PATH = MODEL_DIR / "en_US-lessac-medium.onnx.json"


def download_model():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        print(f"Downloading {CONFIG_PATH.name}...")
        urllib.request.urlretrieve(CONFIG_URL, CONFIG_PATH)
        print("Config downloaded.")

    if not MODEL_PATH.exists() or MODEL_PATH.stat().st_size == 0:
        print(f"Downloading {MODEL_PATH.name} (~35MB)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Model downloaded.")
    else:
        print(f"Piper model already exists at {MODEL_PATH}")


if __name__ == "__main__":
    download_model()
