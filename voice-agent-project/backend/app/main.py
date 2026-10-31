"""FastAPI application factory."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .brain.policy import DialogueManager
from .config import Settings
from .services.scheduler import Scheduler
from .services.sessions import SessionStore


def _clinic_clock(timezone: str) -> Callable[[], dt.datetime]:
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:  # e.g. Windows without the tzdata package
        return dt.datetime.now
    return lambda: dt.datetime.now(zone).replace(tzinfo=None)


def create_app(clock: Callable[[], dt.datetime] | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    clock = clock or _clinic_clock(settings.timezone)

    app = FastAPI(title="Green Valley Clinic Voice Agent", version="1.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
    scheduler = Scheduler(clock)
    app.state.scheduler = scheduler
    app.state.manager = DialogueManager(scheduler, clock)
    app.state.sessions = SessionStore(settings.session_ttl_seconds)
    app.include_router(router)
    return app


app = create_app()
