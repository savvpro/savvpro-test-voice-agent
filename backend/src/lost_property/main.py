from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from lost_property.api.schemas import ErrorResponse, Health, SessionView, Transcription, TurnRequest
from lost_property.api.security import COOKIE, Limiter, SecurityMiddleware
from lost_property.application.service import AppError, ConversationService, token_hash
from lost_property.application.speech import GroqTranscriber
from lost_property.config import Settings
from lost_property.persistence.database import Database


def utcnow() -> datetime:
    return datetime.now(UTC)


def create_app(
    settings: Settings | None = None,
    *,
    clock: Callable[[], datetime] = utcnow,
    speech_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    config = settings or Settings()
    database = Database(config.database_url)
    service, limiter = ConversationService(database, config, clock), Limiter()
    transcriber = GroqTranscriber(config, speech_transport)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if database.ready():
            database.cleanup(clock().timestamp(), config.idle_seconds)
        try:
            yield
        finally:
            await transcriber.close()
            database.engine.dispose()

    app = FastAPI(
        title="Riverside Lost Property",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.state.db = database
    app.add_middleware(SecurityMiddleware, settings=config)

    @app.exception_handler(AppError)
    async def application_error(request: Request, error: AppError) -> JSONResponse:
        response = JSONResponse(
            {
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "request_id": request.state.request_id,
                }
            },
            status_code=error.status,
        )
        if error.status == 401:
            response.delete_cookie(COOKIE, path="/api")
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
        return await application_error(
            request,
            AppError(
                422,
                "INVALID_INPUT",
                "Check the request format and keep each message between 1 and 1,000 characters.",
            ),
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, _: SQLAlchemyError) -> JSONResponse:
        return await application_error(
            request,
            AppError(
                503,
                "STORAGE_UNAVAILABLE",
                "The service could not save your request. Retry the same message shortly.",
            ),
        )

    @app.get("/health/live", response_model=Health)
    def live() -> Health:
        return Health(status="ok")

    @app.get("/health/ready", response_model=Health)
    def ready() -> Health:
        if not database.ready():
            raise AppError(503, "NOT_READY", "The service is starting. Please try again shortly.")
        return Health(status="ready")

    errors: dict[int | str, dict[str, object]] = {
        status: {"model": ErrorResponse} for status in (401, 403, 409, 413, 422, 429, 503)
    }

    @app.post("/api/v1/session", response_model=SessionView, responses=errors)
    def open_session(request: Request, response: Response) -> SessionView:
        # Rate-limit opening even if the old session is invalid or expired.
        address = request.client.host if request.client else "unknown"
        limiter.take("open:" + address, config.session_limit, 600)
        view, capability = service.open(request.cookies.get(COOKIE))
        if capability:
            response.set_cookie(
                COOKIE,
                capability,
                max_age=config.absolute_seconds,
                httponly=True,
                secure=config.secure_cookies,
                samesite="strict",
                path="/api",
            )
        return view

    @app.get("/api/v1/session", response_model=SessionView, responses=errors)
    def get_session(request: Request) -> SessionView:
        return service.get(request.cookies.get(COOKIE))

    @app.post("/api/v1/turns", response_model=SessionView, responses=errors)
    def turn(request: Request, body: TurnRequest) -> SessionView:
        token = request.cookies.get(COOKIE)
        if token:
            limiter.take("turn:" + token_hash(token), config.turn_limit, 60)
        return service.turn(token, body)

    @app.delete("/api/v1/session", status_code=204, responses=errors)
    def erase_session(request: Request) -> Response:
        service.erase(request.cookies.get(COOKIE))
        response = Response(status_code=204)
        response.delete_cookie(COOKIE, path="/api")
        return response

    @app.post(
        "/api/v1/transcriptions",
        response_model=Transcription,
        responses=errors,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    mime: {"schema": {"type": "string", "format": "binary"}}
                    for mime in ("audio/webm", "audio/mp4", "audio/ogg", "audio/wav")
                },
            }
        },
    )
    async def transcribe(request: Request) -> Transcription:
        token = request.cookies.get(COOKIE)
        await run_in_threadpool(service.get, token)
        limiter.take("speech:" + token_hash(token or ""), 12, 60)
        transcript = await transcriber.transcribe(
            await request.body(), request.headers.get("content-type", "")
        )
        return Transcription(text=transcript)

    if config.static_directory:
        directory = Path(config.static_directory).resolve()
        app.mount("/", StaticFiles(directory=directory, html=True), name="web")
    return app
