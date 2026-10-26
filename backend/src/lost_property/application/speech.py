import asyncio

import httpx

from lost_property.application.service import AppError
from lost_property.config import Settings

ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3"
AUDIO_TYPES = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "video/mp4": "mp4",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


def validate_audio(audio: bytes, content_type: str, maximum: int) -> str:
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime not in AUDIO_TYPES:
        raise AppError(
            415,
            "UNSUPPORTED_AUDIO",
            "Use a browser that records WebM, Ogg, MP4, or WAV audio, or type instead.",
        )
    if len(audio) > maximum:
        raise AppError(
            413, "AUDIO_TOO_LARGE", "The recording is too large. Please record a shorter message."
        )
    extension = AUDIO_TYPES[mime]
    signatures = {
        "webm": audio.startswith(b"\x1a\x45\xdf\xa3"),
        "ogg": audio.startswith(b"OggS"),
        "mp4": audio[4:8] == b"ftyp",
        "wav": audio.startswith(b"RIFF") and audio[8:12] == b"WAVE",
    }
    if len(audio) < 16 or not signatures[extension]:
        raise AppError(
            422,
            "INVALID_AUDIO",
            "The recording could not be read. Please record again or type your message.",
        )
    return extension


class GroqTranscriber:
    """Audio-to-text only. Inventory and dialogue state never reach Groq."""

    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(45, connect=10),
            transport=transport,
            trust_env=False,
            follow_redirects=False,
        )
        self.capacity = asyncio.Semaphore(2)

    async def close(self) -> None:
        await self.client.aclose()

    async def transcribe(self, audio: bytes, content_type: str) -> str:
        extension = validate_audio(audio, content_type, self.settings.audio_max_bytes)
        if not self.settings.groq_api_key.strip():
            raise AppError(
                503,
                "VOICE_NOT_CONFIGURED",
                "Voice input is temporarily unavailable. You can continue by typing.",
            )
        try:
            async with asyncio.timeout(50), self.capacity:
                response = await self.client.post(
                    ENDPOINT,
                    headers={"Authorization": f"Bearer {self.settings.groq_api_key}"},
                    files={
                        "file": (f"recording.{extension}", audio, content_type.split(";", 1)[0])
                    },
                    data={
                        "model": MODEL,
                        "language": "en",
                        "response_format": "verbose_json",
                        "temperature": "0",
                    },
                )
        except (httpx.HTTPError, TimeoutError) as error:
            raise AppError(
                503,
                "SPEECH_UNAVAILABLE",
                "The speech service did not respond. Try again or type your message.",
            ) from error
        if response.status_code == 429:
            raise AppError(
                429,
                "SPEECH_RATE_LIMIT",
                "The speech service is busy. Wait briefly, or continue by typing.",
            )
        if response.status_code in (400, 413, 415, 422):
            raise AppError(
                422,
                "INVALID_AUDIO",
                "The speech service could not read this recording. Please try again or type.",
            )
        if response.status_code != 200:
            raise AppError(
                503,
                "SPEECH_UNAVAILABLE",
                "Voice input is temporarily unavailable. You can continue by typing.",
            )
        try:
            data = response.json()
        except ValueError as error:
            raise AppError(
                503, "SPEECH_UNAVAILABLE", "The speech reply could not be read. Please try again."
            ) from error
        transcript = data.get("text") if isinstance(data, dict) else None
        if not isinstance(transcript, str) or not transcript.strip():
            raise AppError(
                422,
                "NO_SPEECH",
                "No clear speech was detected. Please try again or type your message.",
            )
        if len(transcript.strip()) > 1000:
            raise AppError(
                422,
                "SPEECH_TOO_LONG",
                "Please use a shorter spoken message, or type your description.",
            )
        segments = data.get("segments", [])
        if (
            isinstance(segments, list)
            and segments
            and all(
                isinstance(segment, dict)
                and isinstance(segment.get("no_speech_prob"), (int, float))
                and segment["no_speech_prob"] >= 0.8
                for segment in segments
            )
        ):
            raise AppError(
                422,
                "NO_SPEECH",
                "No clear speech was detected. Please try again or type your message.",
            )
        return transcript.strip()
