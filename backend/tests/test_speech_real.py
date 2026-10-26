"""Real models, real audio: Piper speaks, Whisper listens.

Slow and needs the downloaded models, so it only runs with ``RUN_SLOW=1``
(``make test-slow``) and skips if the models aren't there.
"""

import pytest

from app.config import get_settings
from app.speech.stt import FasterWhisperSTT, build_initial_prompt
from app.speech.tts import PiperTTS

pytestmark = pytest.mark.slow


def test_piper_audio_round_trips_through_whisper(clinic, classifier):
    from app.db.repository import ClinicRepository
    from app.nlu.pipeline import parse
    from tests.conftest import CALL_NOW

    settings = get_settings()
    if not settings.piper_voice_path.exists() or not settings.whisper_dir.exists():
        pytest.skip("speech models not downloaded: python scripts/download_models.py")

    by_department = ClinicRepository(clinic).doctors_by_department()
    prompt = build_initial_prompt(list(by_department), sum(by_department.values(), []))
    tts = PiperTTS(settings.piper_voice_path)
    stt = FasterWhisperSTT(
        settings.stt_model,
        settings.stt_device,
        settings.stt_compute_type,
        str(settings.whisper_dir),
        initial_prompt=prompt,
    )

    wav = tts.synthesize("I'd like to see a cardiologist on Friday at eleven, please.")
    heard = stt.transcribe(wav)

    words = heard.text.lower()
    for key in ("cardiologist", "friday", "11"):
        assert key in words, heard.text
    assert heard.confidence and heard.confidence > 0.5
    nlu = parse(heard.text, now=CALL_NOW, classifier=classifier)
    assert nlu.entities.department == "Cardiology"
