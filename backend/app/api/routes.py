"""HTTP endpoints for the call screen."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.clinic.calendar import SERVICE_LABELS, say_slot

router = APIRouter(prefix="/api")


class TurnIn(BaseModel):
    text: str = Field("", max_length=500)


def _store(request: Request):
    return request.app.state.store


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/calls", status_code=201)
def start_call(request: Request) -> dict:
    store = _store(request)
    with store.lock:
        call_id, call, greeting = store.start()
        return {"call_id": call_id, "reply": greeting, "state": call.snapshot(), "ended": False}


@router.post("/calls/{call_id}/turns")
def take_turn(call_id: str, body: TurnIn, request: Request) -> dict:
    store = _store(request)
    with store.lock:
        found = store.get(call_id)
        if not found:
            raise HTTPException(404, "Call not found. Start a new call.")
        call, log = found
        call.now = store.clock()
        decision = asdict(call.turn(body.text))
        log.append(decision)
        return decision


@router.get("/calls/{call_id}")
def get_call(call_id: str, request: Request) -> dict:
    found = _store(request).get(call_id)
    if not found:
        raise HTTPException(404, "Call not found.")
    call, log = found
    return {"call_id": call_id, "turns": log, "state": call.snapshot(), "ended": call.s.ended}


@router.get("/schedule")
def schedule(request: Request) -> dict:
    store = _store(request)
    today = store.clock().date()
    bookings = sorted(store.calendar.bookings.values(), key=lambda b: b.start)
    return {
        "bookings": [
            {
                "id": b.id,
                "name": b.name,
                "phone": f"ends in {b.phone[-4:]}" if b.phone else "not given",
                "service": SERVICE_LABELS[b.service],
                "start": b.start.isoformat(),
                "when": say_slot(b.start, today),
            }
            for b in bookings
        ]
    }


@router.post("/reset")
def reset(request: Request) -> dict:
    store = _store(request)
    with store.lock:
        store.reset()
    return {"status": "reset"}
