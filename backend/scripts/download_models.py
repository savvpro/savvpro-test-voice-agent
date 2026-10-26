"""Download the speech models into backend/models (run from backend/).

    python scripts/download_models.py

Fetches the Piper voice (.onnx + .onnx.json) from the rhasspy/piper-voices
repository on Hugging Face, and pre-downloads the faster-whisper model so the
first call doesn't wait for it. Files that already exist are skipped.
"""

import ssl
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402

PIPER_VOICES_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"


def piper_voice_url(voice: str, suffix: str) -> str:
    """en_US-lessac-medium -> .../en/en_US/lessac/medium/en_US-lessac-medium<suffix>"""
    locale, name, quality = voice.split("-", 2)
    language = locale.split("_")[0]
    return f"{PIPER_VOICES_URL}/{language}/{locale}/{name}/{quality}/{voice}{suffix}"


def _ssl_context() -> ssl.SSLContext:
    # python.org builds on macOS ship without CA certificates; certifi comes with httpx.
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def download(url: str, target: Path) -> None:
    if target.exists():
        print(f"  have {target.name}")
        return
    print(f"  get  {url}")
    partial = target.with_name(target.name + ".part")
    with (
        urllib.request.urlopen(url, timeout=60, context=_ssl_context()) as response,
        partial.open("wb") as out,
    ):
        while chunk := response.read(1 << 20):
            out.write(chunk)
    partial.rename(target)  # only a complete file gets the real name


def main() -> None:
    settings = get_settings()
    settings.models_dir.mkdir(parents=True, exist_ok=True)

    print(f"Piper voice {settings.tts_voice} -> {settings.models_dir}")
    for suffix in (".onnx", ".onnx.json"):
        download(
            piper_voice_url(settings.tts_voice, suffix),
            settings.models_dir / (settings.tts_voice + suffix),
        )

    print(f"Whisper {settings.stt_model} -> {settings.whisper_dir}")
    from faster_whisper import WhisperModel

    WhisperModel(
        settings.stt_model,
        device=settings.stt_device,
        compute_type=settings.stt_compute_type,
        download_root=str(settings.whisper_dir),
    )
    print("Done.")


if __name__ == "__main__":
    main()
