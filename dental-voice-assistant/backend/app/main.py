"""FastAPI application factory with Voice Pipeline lifespan management."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from voice_agent.stt.fake_stt import FakeSTT
from voice_agent.tts.fake_tts import FakeTTS

from app.api import appointments, clinic, health, ws_calls
from app.config import settings
from app.db.engine import engine
from app.db.models import Base
from app.logging_config import configure_logging
from app.services.session_store import SessionStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: configure logging, database, and voice models. Shutdown: dispose engine."""
    configure_logging(settings.log_level)

    # In production, Alembic manages migrations. Here we ensure tables exist.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize Voice Session Store
    if not hasattr(app.state, "session_store") or app.state.session_store is None:
        app.state.session_store = SessionStore(
            ttl_seconds=settings.session_ttl_seconds,
            max_size=settings.session_max_size,
        )

    # Active calls counter
    if not hasattr(app.state, "active_calls"):
        app.state.active_calls = 0

    # Initialize STT Engine
    if not hasattr(app.state, "stt") or app.state.stt is None:
        if settings.stt_provider.lower() == "fake":
            logger.info("Initializing FakeSTT engine for app.state.stt")
            app.state.stt = FakeSTT()
        else:
            try:
                from voice_agent.stt.faster_whisper_stt import FasterWhisperSTT

                logger.info(
                    "Loading Whisper model '%s' (device: %s, compute: %s)...",
                    settings.whisper_model,
                    settings.whisper_device,
                    settings.whisper_compute_type,
                )
                app.state.stt = FasterWhisperSTT(
                    model_size_or_path=settings.whisper_model,
                    device=settings.whisper_device,
                    compute_type=settings.whisper_compute_type,
                )
            except Exception as exc:
                logger.warning("Could not load FasterWhisperSTT: %s. Falling back to FakeSTT.", exc)
                app.state.stt = FakeSTT()

    # Initialize TTS Engine
    if not hasattr(app.state, "tts") or app.state.tts is None:
        if settings.tts_provider.lower() == "fake":
            logger.info("Initializing FakeTTS engine for app.state.tts")
            app.state.tts = FakeTTS()
        elif settings.tts_provider.lower() == "piper":
            from voice_agent.tts.piper_engine import PiperTTS

            app.state.tts = PiperTTS()
        else:
            from voice_agent.tts.edge_tts_engine import EdgeTTS

            app.state.tts = EdgeTTS(voice=settings.tts_voice)

    yield

    await engine.dispose()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.clinic_name,
        description="Voice assistant REST API for BrightSmile Dental Clinic.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(clinic.router)
    app.include_router(appointments.router)
    app.include_router(ws_calls.router)

    return app


app = create_app()
