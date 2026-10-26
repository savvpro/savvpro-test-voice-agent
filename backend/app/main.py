"""FastAPI entrypoint for the Harbor Lights booking assistant."""

from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.db import init_db, ping_db
from app.engine import availability
from app.engine.availability import SERVICE_TIMES, TABLES
from app.engine.dialogue import DialogueEngine
from app.models import (
    AdminStats,
    Booking,
    BookingListResponse,
    OpenSlotsResponse,
    ResetRequest,
    SeedResponse,
    TurnRequest,
    TurnResponse,
)
from app.rate_limit import rate_limit_enabled, turn_limiter

logger = logging.getLogger("harbor.api")
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info("SQLite ready at %s", availability.active_db_path())
    yield


app = FastAPI(
    title="Harbor Lights Voice Booking",
    description=(
        "Deterministic voice booking brain — no LLM, no paid APIs. "
        "SQLite-backed with local rate limits and fake confirmation logs."
    ),
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = DialogueEngine()


def _admin_password() -> str:
    return os.environ.get("ADMIN_PASSWORD", "admin")


def _require_admin(password: Optional[str]) -> None:
    if not password or password != _admin_password():
        raise HTTPException(status_code=401, detail="Invalid admin password")


def _booking_model(r) -> Booking:
    return Booking(
        id=r.id,
        restaurant=r.restaurant,
        date=r.date,
        time=r.time,
        party_size=r.party_size,
        guest_name=r.guest_name,
        table_label=r.table_label,
        status=getattr(r, "status", "active"),
        created_at=r.created_at,
    )


@app.middleware("http")
async def request_logging(request: Request, call_next):
    req_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    started = time.perf_counter()
    response: Response | None = None
    try:
        response = await call_next(request)
        return response
    finally:
        ms = (time.perf_counter() - started) * 1000
        status = response.status_code if response is not None else 500
        if response is not None:
            response.headers["X-Request-Id"] = req_id
            response.headers["X-Response-Time-Ms"] = f"{ms:.1f}"
        logger.info(
            "request_id=%s method=%s path=%s status=%s latency_ms=%.1f",
            req_id,
            request.method,
            request.url.path,
            status,
            ms,
        )


@app.get("/api/health")
def health() -> dict:
    db_ok = ping_db()
    try:
        count = availability.store.count_bookings()
        active = availability.store.count_bookings(active_only=True)
    except Exception:
        count = -1
        active = -1
    return {
        "ok": db_ok,
        "service": "harbor-lights-booking",
        "version": "1.2.0",
        "persistence": "sqlite",
        "db_ok": db_ok,
        "booking_count": count,
        "active_bookings": active,
        "tables": len(TABLES),
        "service_times": SERVICE_TIMES,
        "rate_limit_enabled": rate_limit_enabled(),
    }


@app.post("/api/turn", response_model=TurnResponse)
def turn(req: TurnRequest, request: Request) -> TurnResponse:
    if rate_limit_enabled():
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{req.session_id}"
        if not turn_limiter.allow(key):
            raise HTTPException(
                status_code=429,
                detail="Too many turns — slow down and try again shortly.",
            )
    return engine.handle_turn(req.session_id, req.text)


@app.post("/api/reset", response_model=TurnResponse)
def reset(req: ResetRequest) -> TurnResponse:
    return engine.reset(req.session_id)


# ── Admin (trivial shared password; local / assessment only) ──────────────


@app.get("/api/admin/bookings", response_model=BookingListResponse)
def admin_list_bookings(
    date: Optional[str] = Query(None, description="Filter YYYY-MM-DD"),
    q: Optional[str] = Query(None, description="Search booking id substring"),
    include_cancelled: bool = Query(True),
    x_admin_password: Optional[str] = Header(None, alias="X-Admin-Password"),
) -> BookingListResponse:
    _require_admin(x_admin_password)
    rows = availability.store.list_bookings(
        date_=date, booking_id=q, include_cancelled=include_cancelled
    )
    return BookingListResponse(bookings=[_booking_model(r) for r in rows])


@app.delete("/api/admin/bookings/{booking_id}")
def admin_cancel_booking(
    booking_id: str,
    x_admin_password: Optional[str] = Header(None, alias="X-Admin-Password"),
) -> dict:
    _require_admin(x_admin_password)
    ok = availability.store.cancel_booking(booking_id)
    if not ok:
        raise HTTPException(
            status_code=404, detail="Booking not found or already cancelled"
        )
    return {"ok": True, "cancelled": booking_id, "status": "cancelled"}


@app.post("/api/admin/bookings/{booking_id}/restore")
def admin_restore_booking(
    booking_id: str,
    x_admin_password: Optional[str] = Header(None, alias="X-Admin-Password"),
) -> dict:
    _require_admin(x_admin_password)
    ok = availability.store.restore_booking(booking_id)
    if not ok:
        raise HTTPException(
            status_code=409,
            detail="Cannot restore — missing, not cancelled, or table taken",
        )
    return {"ok": True, "restored": booking_id, "status": "active"}


@app.get("/api/admin/open-slots", response_model=OpenSlotsResponse)
def admin_open_slots(
    date: str = Query(..., description="YYYY-MM-DD"),
    party_size: int = Query(2, ge=1, le=20),
    x_admin_password: Optional[str] = Header(None, alias="X-Admin-Password"),
) -> OpenSlotsResponse:
    _require_admin(x_admin_password)
    return OpenSlotsResponse(
        date=date,
        party_size=party_size,
        open_times=availability.store.open_slots(date, party_size),
    )


@app.get("/api/admin/stats", response_model=AdminStats)
def admin_stats(
    x_admin_password: Optional[str] = Header(None, alias="X-Admin-Password"),
) -> AdminStats:
    _require_admin(x_admin_password)
    return AdminStats(**availability.store.stats())


@app.get("/api/admin/bookings.csv")
def admin_export_csv(
    date: Optional[str] = Query(None),
    include_cancelled: bool = Query(True),
    x_admin_password: Optional[str] = Header(None, alias="X-Admin-Password"),
) -> PlainTextResponse:
    _require_admin(x_admin_password)
    body = availability.store.export_csv(
        date_=date, include_cancelled=include_cancelled
    )
    return PlainTextResponse(
        body,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bookings.csv"},
    )


@app.post("/api/admin/seed", response_model=SeedResponse)
def admin_seed(
    x_admin_password: Optional[str] = Header(None, alias="X-Admin-Password"),
) -> SeedResponse:
    _require_admin(x_admin_password)
    created = availability.store.seed_demo()
    return SeedResponse(
        ok=True, created=len(created), ids=[c.id for c in created]
    )
