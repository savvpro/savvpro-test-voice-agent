"""One call turn end to end: STT -> NLU -> dialogue manager -> TTS.

The service owns no global state: the DB session factory, classifier and
speech engines are passed in, so tests run it against an in-memory database
with fake speech.
"""

import base64
import datetime as dt
import logging
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.clock import clinic_now
from app.config import Settings, get_settings
from app.db.repository import ClinicRepository
from app.dialogue.manager import Decision, DialogueManager
from app.nlu.classifier import IntentClassifier
from app.nlu.pipeline import NLUResult, parse
from app.schemas import DecisionOut, Timings, TurnResponse
from app.services.session_store import CallSession, HistoryEntry, SessionStore
from app.speech.stt import SpeechToText, Transcription, build_initial_prompt, build_stt
from app.speech.tts import TextToSpeech, build_tts

logger = logging.getLogger(__name__)


class SpeechUnavailableError(RuntimeError):
    """Audio was sent but no speech-to-text engine is loaded."""


class AudioNotUnderstoodError(ValueError):
    """The speech-to-text engine could not decode the uploaded audio."""


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


class ConversationService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: SessionStore,
        classifier: IntentClassifier,
        stt: SpeechToText | None,
        tts: TextToSpeech,
        now: Callable[[], dt.datetime] = clinic_now,
        seed: int | None = None,
    ):
        self.session_factory = session_factory
        self.store = store
        self.classifier = classifier
        self.stt = stt
        self.tts = tts
        self.now = now
        self.seed = seed  # fixed reply variants in tests; random per call otherwise

    def start(self) -> TurnResponse:
        call = self.store.create(seed=self.seed)
        with call.lock:
            decision, dm_ms = self._decide(call, None)
            return self._respond(call, decision, None, None, Timings(dm=dm_ms))

    def get(self, session_id: str) -> CallSession:
        return self.store.get(session_id)

    def turn(
        self, session_id: str, text: str | None = None, audio: bytes | None = None
    ) -> TurnResponse:
        call = self.store.get(session_id)
        with call.lock:
            timings = Timings()
            confidence = None
            if audio is not None:
                heard = self._transcribe(audio)
                timings.stt = heard[1]
                text, confidence = heard[0].text, heard[0].confidence
            text = (text or "").strip()

            start = time.perf_counter()
            nlu = parse(
                text,
                expected_slot=call.frame.expected_slot,
                now=self.now(),
                classifier=self.classifier,
            )
            timings.nlu = _ms(start)

            call.history.append(HistoryEntry("caller", text, self.now()))
            decision, timings.dm = self._decide(call, nlu)
            response = self._respond(call, decision, text, nlu, timings)
            response.transcript_confidence = confidence
            return response

    # --- steps -------------------------------------------------------------

    def _transcribe(self, audio: bytes) -> tuple[Transcription, float]:
        if self.stt is None:
            raise SpeechUnavailableError("speech recognition is not available, send text instead")
        start = time.perf_counter()
        try:
            heard = self.stt.transcribe(audio)
        except Exception as exc:
            logger.warning("could not transcribe %d bytes of audio: %s", len(audio), exc)
            raise AudioNotUnderstoodError("could not read the audio") from exc
        return heard, _ms(start)

    def _decide(self, call: CallSession, nlu: NLUResult | None) -> tuple[Decision, float]:
        start = time.perf_counter()
        with self.session_factory() as db:
            repo = ClinicRepository(db, now=self.now)
            # A fresh manager per turn (the repo is bound to this turn's DB session);
            # the seed moves on each turn so phrasing still varies within a call.
            manager = DialogueManager(repo, seed=call.seed + len(call.history))
            decision = manager.start(call.frame) if nlu is None else manager.handle(nlu, call.frame)
        call.ended = call.ended or decision.end_call
        call.history.append(HistoryEntry("agent", decision.reply_text, self.now()))
        return decision, _ms(start)

    def _speak(self, text: str) -> tuple[str | None, float]:
        start = time.perf_counter()
        try:
            audio = self.tts.synthesize(text)
        except Exception as exc:  # a broken voice must not break the call
            logger.warning("text-to-speech failed, replying with text only: %s", exc)
            audio = None
        encoded = base64.b64encode(audio).decode("ascii") if audio else None
        return encoded, _ms(start)

    def _respond(
        self,
        call: CallSession,
        decision: Decision,
        transcript: str | None,
        nlu: NLUResult | None,
        timings: Timings,
    ) -> TurnResponse:
        audio, timings.tts = self._speak(decision.reply_text)
        return TurnResponse(
            session_id=call.id,
            transcript=transcript,
            nlu=nlu,
            decision=DecisionOut(
                state=decision.state,
                action=decision.action,
                frame=decision.frame,
                end_call=decision.end_call,
                expected_slot=decision.expected_slot,
            ),
            reply_text=decision.reply_text,
            audio_base64=audio,
            audio_mime=self.tts.mime if audio else None,
            timings_ms=timings,
        )


def prepare_database(session_factory: Callable[[], Session]) -> None:
    """Create tables, and seed the fake clinic if the database is empty."""
    from app.db.repository import list_departments
    from app.db.seed import seed_database
    from app.db.session import init_db

    init_db()
    with session_factory() as db:
        if not list_departments(db):
            summary = seed_database(db, start=clinic_now().date())
            logger.info("empty database: seeded %d slots", summary.slots)


def build_conversation_service(settings: Settings | None = None) -> ConversationService:
    """The real service: on-disk database, trained classifier, speech engines from settings."""
    from app.db.session import SessionLocal
    from app.nlu.classifier import get_classifier

    settings = settings or get_settings()
    prepare_database(SessionLocal)
    with SessionLocal() as db:
        by_department = ClinicRepository(db).doctors_by_department()
    prompt = build_initial_prompt(
        list(by_department), [d for doctors in by_department.values() for d in doctors]
    )
    classifier = get_classifier()
    parse("book me for tomorrow at 10", classifier=classifier)  # warm up the first-call caches
    return ConversationService(
        session_factory=SessionLocal,
        store=SessionStore(),
        classifier=classifier,
        stt=build_stt(settings, initial_prompt=prompt),
        tts=build_tts(settings),
    )
