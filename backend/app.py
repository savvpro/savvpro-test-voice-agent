import logging
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend import store
from backend.brain import WELCOME, decide
from backend.database import Base, CallerSession, ProcessedTurn, make_engine
from backend.domain import SERVICES, clock, utc_naive

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env.local", ".env"), extra="ignore")
    database_url: str = "sqlite:///./workshop.db"
    groq_api_key: SecretStr = SecretStr("")
    secure_cookies: bool = False


class TurnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn_id: str = Field(min_length=8, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    revision: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=1000)


class ResetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)


def snapshot(db: Session, caller: CallerSession, now: datetime) -> dict[str, Any]:
    history = list(
        db.scalars(
            select(ProcessedTurn)
            .where(ProcessedTurn.session_id == caller.id)
            .order_by(ProcessedTurn.revision.desc())
            .limit(30)
        )
    )
    seed_day = min((a.start for a in store.owned(db, caller.id, now)), default=None)
    return {
        "revision": caller.revision,
        "state": caller.state,
        "appointments": [store.summary(a) for a in store.owned(db, caller.id, now)],
        "history": [
            {"text": row.text, "reply": row.response["reply"], "trace": row.response["trace"]}
            for row in reversed(history)
        ],
        "welcome": WELCOME,
        "caller": "Alex Rivera",
        "timezone": "Asia/Karachi",
        "demo_date": store.from_utc(seed_day).date().isoformat()
        if seed_day
        else now.date().isoformat(),
    }


def create_app(
    database_url: str | None = None,
    now: Callable[[], datetime] = clock,
    database_engine: Engine | None = None,
) -> FastAPI:
    settings = Settings()
    engine = (
        database_engine
        if database_engine is not None
        else make_engine(database_url or settings.database_url)
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Initialization only: create_all never upgrades or drops existing tables.
        Base.metadata.create_all(bind=engine)
        yield
        engine.dispose()

    app = FastAPI(title="Bayline deterministic reception", lifespan=lifespan)
    app.state.engine = engine
    app.state.settings = settings
    counts: dict[str, deque[float]] = defaultdict(deque)
    count_lock = threading.Lock()

    @app.middleware("http")
    async def boundaries(request: Request, call_next: Any) -> Response:
        if request.url.path.startswith("/api/"):
            if request.method == "POST":
                origin = request.headers.get("origin")
                if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
                    return JSONResponse(
                        {"detail": "Cross-origin writes are not allowed."}, status_code=403
                    )
                length = request.headers.get("content-length", "0")
                if not length.isdigit() or int(length) > 6 * 1024 * 1024:
                    return JSONResponse(
                        {"detail": "Request exceeds the 6 MB limit."}, status_code=413
                    )
                key = (request.client.host if request.client else "unknown") + (
                    "stt" if request.url.path == "/api/stt" else "api"
                )
                stamp = time.monotonic()
                with count_lock:
                    for expired in [
                        k for k, values in counts.items() if not values or values[-1] < stamp - 60
                    ]:
                        counts.pop(expired, None)
                    queue = counts[key]
                    while queue and queue[0] < stamp - 60:
                        queue.popleft()
                    limit = 20 if request.url.path == "/api/stt" else 90
                    if len(queue) >= limit:
                        return JSONResponse(
                            {"detail": "Too many requests. Please wait a minute."},
                            status_code=429,
                            headers={"Retry-After": "60"},
                        )
                    queue.append(stamp)
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "microphone=(self), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response

    def caller_for(db: Session, request: Request) -> CallerSession:
        sid = request.cookies.get("bayline_session", "")
        caller = db.get(CallerSession, sid)
        if caller is None:
            raise HTTPException(401, "Session expired. Reload to start a new demo.")
        return caller

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_: Request, error: SQLAlchemyError) -> JSONResponse:
        # Do not log connection strings or SQL parameters from exception messages.
        logger.error("Database operation failed: %s", type(error).__name__)
        return JSONResponse(
            {"detail": "The booking service is temporarily unavailable. Please retry."},
            status_code=503,
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "brain": "deterministic-python"}

    @app.get("/api/capabilities")
    def capabilities() -> dict[str, Any]:
        return {
            "server_stt": bool(settings.groq_api_key.get_secret_value()),
            "services": SERVICES,
            "timezone": "Asia/Karachi",
        }

    @app.post("/api/session")
    def session(request: Request, response: Response) -> dict[str, Any]:
        with Session(engine, expire_on_commit=False) as db, db.begin():
            caller = db.get(CallerSession, request.cookies.get("bayline_session", ""))
            if caller is None:
                caller = CallerSession(
                    id=secrets.token_urlsafe(32), created_at=utc_naive(now()), state={}
                )
                db.add(caller)
                db.flush()
                store.seed(db, caller, now())
                response.set_cookie(
                    "bayline_session",
                    caller.id,
                    httponly=True,
                    secure=settings.secure_cookies,
                    samesite="strict",
                    max_age=86400 * 7,
                )
            return snapshot(db, caller, now())

    @app.get("/api/appointments")
    def appointments(request: Request) -> list[dict[str, Any]]:
        with Session(engine) as db:
            caller = caller_for(db, request)
            return [store.summary(a) for a in store.owned(db, caller.id, now())]

    def cached(db: Session, sid: str, turn: TurnIn) -> dict[str, Any] | None:
        row = db.scalar(
            select(ProcessedTurn).where(
                ProcessedTurn.session_id == sid, ProcessedTurn.turn_id == turn.turn_id
            )
        )
        if row:
            if row.text != turn.text:
                raise HTTPException(409, "That turn_id already belongs to a different message.")
            return row.response
        return None

    @app.post("/api/turn")
    def turn(payload: TurnIn, request: Request) -> dict[str, Any]:
        if not payload.text.strip():
            raise HTTPException(422, "Please provide a non-empty message.")
        for attempt in range(3):
            try:
                with Session(engine, expire_on_commit=False) as db, db.begin():
                    caller = caller_for(db, request)
                    previous = cached(db, caller.id, payload)
                    if previous is not None:
                        return previous
                    claimed = db.execute(
                        update(CallerSession)
                        .where(
                            CallerSession.id == caller.id,
                            CallerSession.revision == payload.revision,
                        )
                        .values(revision=CallerSession.revision + 1)
                        .execution_options(synchronize_session=False)
                    )
                    if claimed.rowcount != 1:  # type: ignore[attr-defined]
                        previous = cached(db, caller.id, payload)
                        if previous is not None:
                            return previous
                        raise HTTPException(
                            409, "This conversation changed. Reload its latest state and try again."
                        )
                    db.refresh(caller)
                    state, reply, trace = decide(db, caller.id, caller.state, payload.text, now())
                    caller.state = state
                    db.flush()
                    result = {
                        "revision": caller.revision,
                        "state": state,
                        "reply": reply,
                        "trace": trace,
                        "appointments": [
                            store.summary(a) for a in store.owned(db, caller.id, now())
                        ],
                    }
                    db.add(
                        ProcessedTurn(
                            session_id=caller.id,
                            turn_id=payload.turn_id,
                            revision=caller.revision,
                            text=payload.text,
                            response=result,
                        )
                    )
                    return result
            except OperationalError as exc:
                if (
                    engine.dialect.name != "sqlite"
                    or "locked" not in str(exc).lower()
                    or attempt == 2
                ):
                    raise
                time.sleep(0.05 * (attempt + 1))
        raise HTTPException(503, "Please retry this turn.")

    @app.post("/api/session/reset")
    def reset(payload: ResetIn, request: Request) -> dict[str, Any]:
        with Session(engine, expire_on_commit=False) as db, db.begin():
            caller = caller_for(db, request)
            claimed = db.execute(
                update(CallerSession)
                .where(
                    CallerSession.id == caller.id,
                    CallerSession.revision == payload.revision,
                )
                .values(revision=CallerSession.revision + 1)
                .execution_options(synchronize_session=False)
            )
            if claimed.rowcount != 1:  # type: ignore[attr-defined]
                raise HTTPException(409, "The conversation changed. Refresh before resetting.")
            db.refresh(caller)
            store.reset(db, caller, now())
            db.flush()
            return snapshot(db, caller, now())

    @app.post("/api/stt")
    async def stt(request: Request, audio: UploadFile = File(...)) -> dict[str, str]:
        with Session(engine) as db:
            caller_for(db, request)
        key = settings.groq_api_key.get_secret_value()
        if not key:
            raise HTTPException(
                503, "Server transcription is not configured. Use browser speech or typed input."
            )
        allowed = {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/mpeg"}
        mime = (audio.content_type or "").split(";")[0]
        if mime not in allowed:
            raise HTTPException(415, "Use WebM, Ogg, MP4, WAV, or MP3 audio.")
        data = await audio.read(5 * 1024 * 1024 + 1)
        await audio.close()
        if not data or len(data) > 5 * 1024 * 1024:
            raise HTTPException(413, "Audio must contain data and be no larger than 5 MB.")
        valid_header = (
            data.startswith((b"RIFF", b"OggS", b"\x1aE\xdf\xa3", b"ID3", b"\xff"))
            or data[4:8] == b"ftyp"
        )
        if not valid_header:
            raise HTTPException(415, "The uploaded file is not a supported audio recording.")
        extension = {
            "audio/webm": "webm",
            "audio/ogg": "ogg",
            "audio/mp4": "mp4",
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/mpeg": "mp3",
        }[mime]
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                upstream = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": "Bearer " + key},
                    files={"file": ("turn." + extension, data, mime)},
                    data={"model": "whisper-large-v3-turbo", "language": "en", "temperature": "0"},
                )
            if upstream.status_code == 429:
                raise HTTPException(
                    429,
                    "The speech provider's free quota is busy. Use browser speech or try later.",
                )
            if upstream.is_error:
                raise HTTPException(502, "Transcription failed. Please retry or use typed input.")
            transcript = upstream.json().get("text", "").strip()
            if not transcript or len(transcript) > 1000:
                raise HTTPException(
                    422, "No usable short utterance was detected. Please try again."
                )
            return {"text": transcript}
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                502, "Speech service unavailable. Browser speech and typing are still available."
            ) from exc

    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(dist / "index.html")

        @app.get("/favicon.svg")
        def favicon() -> FileResponse:
            return FileResponse(dist / "favicon.svg")

    return app


app = create_app()
