import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.api import router
from app.config import Settings, utc_now
from app.db import Database

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, clock: Callable[[], datetime] = utc_now) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.zone  # Fail fast if the configured timezone is invalid.
    database = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.initialize()
        yield
        database.engine.dispose()

    app = FastAPI(title="VoxDesk", version="1.0.0", lifespan=lifespan)
    app.state.database = database
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.exception_handler(SQLAlchemyError)
    async def database_failure(request: Request, error: SQLAlchemyError):
        # Do not expose SQL parameters (which can include names/history) in logs or responses.
        logger.error("Database operation failed: %s", type(error).__name__)
        status = 503 if isinstance(error, OperationalError) else 500
        return JSONResponse(status_code=status, content={"detail": "The database operation could not be completed. Retry the same request; no success has been reported."})

    app.include_router(router(database, settings, clock))
    return app


app = create_app()
