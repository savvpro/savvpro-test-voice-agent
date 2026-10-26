"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_admin, routes_health, routes_session, routes_turn
from app.config import get_settings
from app.logging import configure_logging
from app.services.conversation import ConversationService, build_conversation_service

logger = logging.getLogger(__name__)


def create_app(conversation: ConversationService | None = None) -> FastAPI:
    """Build the app. Tests pass a ready ``conversation``; otherwise it is built at startup."""
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.conversation is None:
            # Loads the classifier and speech models once, not per request.
            app.state.conversation = build_conversation_service()
        yield

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.conversation = conversation
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes_health.router)
    app.include_router(routes_session.router)
    app.include_router(routes_turn.router)
    app.include_router(routes_admin.router)
    return app


app = create_app()
