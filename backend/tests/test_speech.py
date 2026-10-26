"""Speech engines without loading real models: construction, fallbacks, decoding."""

import io
import logging
import math
import wave
from types import SimpleNamespace

import numpy as np
import pytest

from app.config import Settings
from app.speech.stt import FasterWhisperSTT, build_initial_prompt, build_stt, decode_audio
from app.speech.tts import NullTTS, PiperTTS, build_tts


def make_wav(seconds: float = 0.5, rate: int = 22_050, tone: bool = True) -> bytes:
    t = np.arange(int(seconds * rate)) / rate
    samples = (0.3 * np.sin(2 * np.pi * 440 * t) if tone else np.zeros_like(t)) * 32767
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.astype("<i2").tobytes())
    return buffer.getvalue()


def settings(tmp_path, **overrides) -> Settings:
    return Settings(models_dir=tmp_path, **overrides)


# --- decoding ------------------------------------------------------------------


def test_decode_audio_resamples_to_16k_mono_float():
    pcm = decode_audio(make_wav(seconds=0.5, rate=22_050))
    assert pcm.dtype == np.float32
    assert abs(len(pcm) - 8_000) < 400  # 0.5 s at 16 kHz, give or take resampler delay
    assert 0.2 < np.abs(pcm).max() <= 1.0


def test_decode_audio_rejects_garbage():
    with pytest.raises(Exception):  # noqa: B017  (PyAV's error type varies by version)
        decode_audio(b"definitely not audio")


# --- whisper (model replaced by a stand-in) --------------------------------------


class FakeWhisperModel:
    instances: list[FakeWhisperModel] = []

    def __init__(self, model, device, compute_type, download_root, local_files_only):
        self.args = dict(
            model=model,
            device=device,
            compute_type=compute_type,
            root=download_root,
            local_only=local_files_only,
        )
        self.calls: list[dict] = []
        FakeWhisperModel.instances.append(self)

    def transcribe(self, audio, **kwargs):
        self.calls.append({"audio": audio, **kwargs})
        return iter(self.segments), None

    segments = [
        SimpleNamespace(text=" Book me with ", avg_logprob=math.log(0.9), no_speech_prob=0.01),
        SimpleNamespace(text=" Dr. Saima Rauf.", avg_logprob=math.log(0.7), no_speech_prob=0.02),
    ]


@pytest.fixture
def fake_whisper(monkeypatch):
    import faster_whisper

    FakeWhisperModel.instances.clear()
    monkeypatch.setattr(faster_whisper, "WhisperModel", FakeWhisperModel)
    return FakeWhisperModel


def test_whisper_uses_vad_prompt_and_english(fake_whisper):
    stt = FasterWhisperSTT(initial_prompt="Doctors: Dr. Saima Rauf.")
    result = stt.transcribe(make_wav())
    [call] = fake_whisper.instances[0].calls
    assert call["vad_filter"] is True
    assert call["initial_prompt"] == "Doctors: Dr. Saima Rauf."
    assert call["language"] == "en"
    assert isinstance(call["audio"], np.ndarray)
    assert result.text == "Book me with Dr. Saima Rauf."
    assert result.confidence == pytest.approx(0.8)


@pytest.mark.parametrize(
    "segment",
    [
        SimpleNamespace(text=" Thank you for watching.", avg_logprob=-0.3, no_speech_prob=0.1),
        SimpleNamespace(text=" Thanks for watching!", avg_logprob=-0.2, no_speech_prob=0.1),
        SimpleNamespace(text=" Please subscribe.", avg_logprob=-0.4, no_speech_prob=0.2),
        SimpleNamespace(
            text=" Bye now.", avg_logprob=-1.4, no_speech_prob=0.8
        ),  # unsure + no speech
    ],
)
def test_whisper_drops_hallucinated_segments(fake_whisper, monkeypatch, segment):
    real = SimpleNamespace(text=" Cancel my booking.", avg_logprob=-0.2, no_speech_prob=0.01)
    monkeypatch.setattr(FakeWhisperModel, "segments", [segment, real])
    assert FasterWhisperSTT().transcribe(make_wav()).text == "Cancel my booking."


def test_whisper_keeps_quiet_but_confident_speech(fake_whisper, monkeypatch):
    # High no_speech_prob alone isn't enough: Whisper was still sure of the words.
    said = SimpleNamespace(text=" Yes.", avg_logprob=-0.3, no_speech_prob=0.7)
    monkeypatch.setattr(FakeWhisperModel, "segments", [said])
    assert FasterWhisperSTT().transcribe(make_wav()).text == "Yes."


def test_build_stt_reads_settings(fake_whisper, tmp_path):
    stt = build_stt(settings(tmp_path, stt_model="tiny.en"), initial_prompt="hi")
    assert isinstance(stt, FasterWhisperSTT)
    assert fake_whisper.instances[0].args == {
        "model": "tiny.en",
        "device": "cpu",
        "compute_type": "int8",
        "root": str(tmp_path / "whisper"),
        "local_only": True,
    }


def test_build_stt_falls_back_to_text_only_when_model_fails(monkeypatch, tmp_path, caplog):
    import faster_whisper

    def broken(*args, **kwargs):
        raise RuntimeError("model.bin not found")

    monkeypatch.setattr(faster_whisper, "WhisperModel", broken)
    with caplog.at_level(logging.WARNING):
        assert build_stt(settings(tmp_path)) is None
    assert "text input only" in caplog.text


@pytest.mark.parametrize("provider", ["none", "google"])
def test_build_stt_disabled_or_unknown(provider, tmp_path):
    assert build_stt(settings(tmp_path, stt_provider=provider)) is None


def test_initial_prompt_names_every_department_and_doctor():
    prompt = build_initial_prompt(["Cardiology", "ENT"], ["Dr. Saima Rauf", "Dr. Zain Abbas"])
    for word in ("Shifa Care Clinic", "Cardiology", "ENT", "Dr. Saima Rauf", "Dr. Zain Abbas"):
        assert word in prompt


# --- piper (voice replaced by a stand-in) ----------------------------------------


class FakePiperVoice:
    @classmethod
    def load(cls, model_path, config_path=None):
        voice = cls()
        voice.paths = (str(model_path), str(config_path))
        return voice

    def synthesize_wav(self, text, wav_file):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22_050)
        wav_file.writeframes(b"\x00\x01" * len(text))


@pytest.fixture
def fake_piper(monkeypatch):
    import piper

    monkeypatch.setattr(piper, "PiperVoice", FakePiperVoice)


def test_piper_returns_a_wav_file(fake_piper, tmp_path):
    voice = tmp_path / "en_US-lessac-medium.onnx"
    voice.touch()
    tts = PiperTTS(voice)
    assert tts.voice.paths == (str(voice), f"{voice}.json")
    audio = tts.synthesize("Hello")
    with wave.open(io.BytesIO(audio)) as wav:
        assert (wav.getframerate(), wav.getnframes()) == (22_050, 5)
    assert tts.mime == "audio/wav"


def test_build_tts_falls_back_when_voice_missing(fake_piper, tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        tts = build_tts(settings(tmp_path))
    assert isinstance(tts, NullTTS)
    assert "download_models.py" in caplog.text


def test_build_tts_falls_back_when_voice_fails_to_load(monkeypatch, tmp_path):
    import piper

    class Broken:
        @classmethod
        def load(cls, *args, **kwargs):
            raise RuntimeError("onnxruntime failed")

    monkeypatch.setattr(piper, "PiperVoice", Broken)
    (tmp_path / "en_US-lessac-medium.onnx").touch()
    assert isinstance(build_tts(settings(tmp_path)), NullTTS)


def test_build_tts_loads_configured_voice(fake_piper, tmp_path):
    (tmp_path / "en_US-amy-low.onnx").touch()
    tts = build_tts(settings(tmp_path, tts_voice="en_US-amy-low"))
    assert isinstance(tts, PiperTTS)


@pytest.mark.parametrize("provider", ["none", "elevenlabs"])
def test_build_tts_disabled_or_unknown(provider, tmp_path):
    assert isinstance(build_tts(settings(tmp_path, tts_provider=provider)), NullTTS)


def test_null_tts_is_silent():
    assert NullTTS().synthesize("anything") is None
