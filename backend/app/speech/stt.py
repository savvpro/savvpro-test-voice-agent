"""Speech-to-text behind a small interface, so the provider can be swapped or faked."""

import io
import logging
import math
import re
from typing import Protocol

import numpy as np
from pydantic import BaseModel

from app.clinic import CLINIC_NAME
from app.config import Settings

logger = logging.getLogger(__name__)


class Transcription(BaseModel):
    text: str
    confidence: float | None = None  # 0..1, None if the engine doesn't report one


class SpeechToText(Protocol):
    def transcribe(self, audio: bytes) -> Transcription: ...


def build_initial_prompt(departments: list[str], doctors: list[str]) -> str:
    """Whisper's initial prompt: clinic vocabulary it would otherwise misspell."""
    return (
        f"A phone call to {CLINIC_NAME} in Lahore. Departments: {', '.join(departments)}. "
        f"Doctors: {', '.join(doctors)}. Booking references look like SC-4F7K. "
        "Mobile numbers look like 0300 1234567."
    )


SAMPLE_RATE = 16_000  # what Whisper expects

# Whisper's own "probably not speech" thresholds (same values the reference implementation uses).
NO_SPEECH_THRESHOLD = 0.6
LOGPROB_THRESHOLD = -1.0
# Phrases Whisper invents on near-silence (it learned them from video subtitles). Without this,
# a silent push-to-talk can come back as "Thank you for watching. Bye now." and end the call.
_HALLUCINATIONS = re.compile(
    r"^\W*(thanks? (you )?(so much )?for watching|please subscribe|subscribe to|"
    r"like and subscribe|see you (in the )?next (video|time)|subtitles? by)",
    re.IGNORECASE,
)


def _is_hallucination(segment) -> bool:
    if segment.no_speech_prob > NO_SPEECH_THRESHOLD and segment.avg_logprob < LOGPROB_THRESHOLD:
        return True
    return bool(_HALLUCINATIONS.match(segment.text.strip()))


def decode_audio(audio: bytes) -> np.ndarray:
    """Any container PyAV/FFmpeg reads (webm, ogg, wav...) -> 16 kHz mono float32.

    faster-whisper has its own decoder, but 1.2.1 passes an argument that PyAV 19
    removed (``metadata_errors``), so we decode here and hand it a plain array.
    """
    import av

    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks: list[np.ndarray] = []
    with av.open(io.BytesIO(audio), mode="r") as container:
        stream = container.streams.audio[0]
        for frame in container.decode(stream):
            frame.pts = None  # let the resampler keep its own timeline
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):  # flush
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32) / 32768.0


class FasterWhisperSTT:
    """Local Whisper (CTranslate2). Takes webm, ogg or wav bytes; PyAV decodes them."""

    def __init__(
        self,
        model: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        download_root: str | None = None,
        initial_prompt: str | None = None,
        local_files_only: bool = True,
    ):
        from faster_whisper import WhisperModel

        # Local files only: the server never downloads 140 MB on startup;
        # scripts/download_models.py does that once.
        self.model = WhisperModel(
            model,
            device=device,
            compute_type=compute_type,
            download_root=download_root,
            local_files_only=local_files_only,
        )
        self.initial_prompt = initial_prompt

    def transcribe(self, audio: bytes) -> Transcription:
        segments, _info = self.model.transcribe(
            decode_audio(audio),
            language="en",
            beam_size=5,
            vad_filter=True,  # drops silence, so a silent clip becomes "" not a hallucination
            initial_prompt=self.initial_prompt,
            condition_on_previous_text=False,
        )
        # The generator does the actual decoding.
        segments = [s for s in segments if not _is_hallucination(s)]
        text = " ".join(s.text.strip() for s in segments).strip()
        if not segments:
            return Transcription(text=text, confidence=None)
        # avg_logprob is the mean token log-probability; exp() turns it into 0..1.
        confidence = sum(math.exp(s.avg_logprob) for s in segments) / len(segments)
        return Transcription(text=text, confidence=round(confidence, 3))


def build_stt(settings: Settings, initial_prompt: str | None = None) -> SpeechToText | None:
    """The configured engine, or None (text-only) if it is disabled or fails to load."""
    provider = settings.stt_provider.lower()
    if provider == "none":
        logger.info("speech-to-text disabled (STT_PROVIDER=none): text input only")
        return None
    if provider != "faster_whisper":
        logger.warning("unknown STT_PROVIDER %r: text input only", settings.stt_provider)
        return None
    try:
        stt = FasterWhisperSTT(
            model=settings.stt_model,
            device=settings.stt_device,
            compute_type=settings.stt_compute_type,
            download_root=str(settings.whisper_dir),
            initial_prompt=initial_prompt,
        )
    except Exception as exc:
        logger.warning(
            "could not load whisper model %r (%s); text input only. "
            "Run `python scripts/download_models.py`.",
            settings.stt_model,
            exc,
        )
        return None
    logger.info("speech-to-text: faster-whisper %s on %s", settings.stt_model, settings.stt_device)
    return stt
