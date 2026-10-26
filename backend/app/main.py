import logging
import sqlite3
import threading
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app import db, dialogue
from app.config import get_settings

log = logging.getLogger("clinic")
EXPIRY = timedelta(minutes=30)
# ponytail: global lock, single sqlite writer; per-call locks if throughput matters
_lock = threading.Lock()


class TurnRequest(BaseModel):
    text: str = Field(max_length=500)


class DecisionModel(BaseModel):
    intent: str
    entities: dict[str, str]
    state: str
    action: str
    slots: dict[str, str]


class CallResponse(BaseModel):
    call_id: str
    reply: str
    decision: DecisionModel
    ended: bool


def _response(cid: str, reply: str, d: dialogue.Decision, ended: bool) -> CallResponse:
    return CallResponse(
        call_id=cid,
        reply=reply,
        decision=DecisionModel(
            intent=d.intent, entities=d.entities, state=d.state, action=d.action, slots=d.slots
        ),
        ended=ended,
    )


def _save(conn: sqlite3.Connection, cid: str, state: dialogue.CallState, now: datetime) -> None:
    with conn:
        if state.ended:  # ended calls 404 from here on
            conn.execute("DELETE FROM calls WHERE id=?", (cid,))
        else:
            conn.execute(
                "INSERT INTO calls(id, state, updated_at) VALUES (?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET state=excluded.state, "
                "updated_at=excluded.updated_at",
                (cid, state.to_json(), now.isoformat()),
            )


def create_app(db_path: str | None = None) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        conn = db.connect(db_path or settings.database_path)
        db.init_db(conn)
        db.seed(conn, app.state.clock().date())
        app.state.conn = conn
        yield
        conn.close()

    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.state.clock = lambda: datetime.now(settings.timezone).replace(
        tzinfo=None, second=0, microsecond=0
    )
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"])

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/calls", status_code=201)
    def start_call(request: Request) -> CallResponse:
        state, reply, decision = dialogue.start_call()
        cid = str(uuid.uuid4())
        with _lock:
            _save(request.app.state.conn, cid, state, request.app.state.clock())
        return _response(cid, reply, decision, False)

    @app.post("/api/calls/{call_id}/turns", response_model=CallResponse)
    def turn(call_id: str, body: TurnRequest, request: Request) -> CallResponse | Response:
        conn: sqlite3.Connection = request.app.state.conn
        clock: Callable[[], datetime] = request.app.state.clock
        now = clock()
        with _lock:
            try:
                row = conn.execute(
                    "SELECT state, updated_at FROM calls WHERE id=?", (call_id,)
                ).fetchone()
                if row and now - datetime.fromisoformat(row["updated_at"]) > EXPIRY:
                    with conn:
                        conn.execute("DELETE FROM calls WHERE id=?", (call_id,))
                    row = None
                if not row:
                    raise HTTPException(404, "Call not found or expired")
                state, reply, decision = dialogue.handle_turn(
                    dialogue.CallState.from_json(row["state"]), body.text, conn, now
                )
                _save(conn, call_id, state, now)
            except HTTPException:
                raise
            except Exception:
                log.exception("turn failed call_id=%s", call_id)
                return JSONResponse({"detail": "Internal error"}, status_code=500)
        log.info(
            "turn call_id=%s intent=%s action=%s state=%s",
            call_id,
            decision.intent,
            decision.action,
            decision.state,
        )
        return _response(call_id, reply, decision, state.ended)

    return app


app = create_app()
