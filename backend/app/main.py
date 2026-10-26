"""FastAPI application entry point."""

import os
import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.database import DEFAULT_DATABASE_PATH, ReservationStore
from app.services.conversations import ConversationService

# Load environment variables from .env file if present
load_dotenv()

def create_app(
    database_path: str | Path | None = None, *, reference_date: datetime | None = None,
) -> FastAPI:
    """Construct an isolated app; database initialization happens at startup."""
    path = database_path if database_path is not None else os.getenv("DATABASE_PATH", str(DEFAULT_DATABASE_PATH))
    options = {"today": lambda: reference_date.date()} if reference_date is not None else {}
    store = ReservationStore(path, **options)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            store.initialize_database()
        except (sqlite3.Error, OSError):
            # Keep health/session handling available. Storage-dependent turns
            # return sanitized 503 responses and restore their previous state.
            logging.getLogger(__name__).exception("Could not initialize reservation storage")
        yield

    application = FastAPI(
        title="Restaurant Voice Assistant API",
        description="A voice-powered restaurant reservation assistant with a custom decision engine.",
        version="0.1.0", lifespan=lifespan,
    )
    application.state.conversation_service = ConversationService(store, reference_date=reference_date)
    cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in cors_origins_raw.split(",")],
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )
    application.include_router(router, prefix="/api")
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
