"""FastAPI application factory.

Creates the app, configures CORS, sets up structured logging via the
lifespan hook, and registers all route modules.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, sessions
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hook.

    * Initialises structured JSON logging.
    * (Future steps will load fake data here.)
    """
    settings = get_settings()
    setup_logging(settings.log_level)
    log.info("REDELIVER backend starting", extra={"env": settings.app_env})
    yield
    log.info("REDELIVER backend shutting down")


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title="REDELIVER",
        description="Parcel redelivery voice-assistant backend",
        version=settings.app_version,
        lifespan=lifespan,
    )

    # --- CORS ----------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routes --------------------------------------------------------
    app.include_router(health.router)
    app.include_router(sessions.router)

    return app


app = create_app()
