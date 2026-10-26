"""HTTP layer for the deterministic appointment dialogue and schedule."""
from __future__ import annotations
import secrets
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from cryptography.fernet import InvalidToken

from . import config as C
from .db import Database
from .dialogue import Brain, Call
from .email_service import EmailService
from .state_crypto import decrypt_state, encrypt_state

app = FastAPI(title="Children's Specialist Clinic appointment assistant")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
db = Database()
email_service = EmailService(db)


class TurnIn(BaseModel):
    session_id: str
    text: str = Field(default="", max_length=500)       # empty text = caller was silent


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/call")
def start_call():
    call = Call(session_id=secrets.token_urlsafe(32))
    reply = Brain(db, email_service=email_service).start(call)
    db.start_session(call.session_id, encrypt_state(call.to_json()))
    return {"session_id": call.session_id, "reply": reply, "state": call.state, "slots": call.slots,
            "intent": None, "action": "GREETING", "extracted": {}, "expecting": None, "end": False, "trace": []}


@app.post("/api/turn")
def turn(body: TurnIn):
    with db.lock:                                        # one turn at a time per process: no double booking
        raw = db.load_state(body.session_id)
        if raw is None:
            raise HTTPException(404, "Unknown call. Start a new call first.")
        try:
            call = Call.from_json(decrypt_state(raw))
        except (ValueError, TypeError, InvalidToken):
            raise HTTPException(400, "This call session is no longer available. Start a new call.")
        before = call.state
        result = Brain(db, email_service=email_service).handle(call, body.text)
        db.log_turn(call.session_id, call.turn, "[redacted]", result.intent, {}, before,
                    call.state, result.action, result.reply)
        db.save_state(call.session_id, encrypt_state(call.to_json()), ended=result.end, outcome=call.outcome)
    safe_slots = {key: result.slots[key] for key in ("date", "token", "time") if result.slots.get(key) is not None}
    return {
        "session_id": call.session_id,
        "reply": result.reply,
        "intent": result.intent,
        "extracted": {"fields_provided": [key for key, value in result.extracted.items() if value]},
        "action": result.action,
        "state": result.state,
        "expecting": result.expecting,
        "slots": safe_slots,
        "end": result.end,
        "trace": result.trace,
        "appointment": result.appointment,
    }


@app.get("/api/schedule")
def schedule(date: str):
    try:
        return db.schedule(date)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


def require_staff(authorization: Optional[str]):
    if not C.STAFF_API_KEY:
        raise HTTPException(503, "Staff record access is not configured.")
    supplied = authorization[len("Bearer "):].strip() if authorization and authorization.startswith("Bearer ") else ""
    if not secrets.compare_digest(supplied, C.STAFF_API_KEY):
        raise HTTPException(401, "Staff authorization required.")


@app.get("/api/appointments")
def appointments(date: Optional[str] = Query(default=None), authorization: Optional[str] = Header(default=None)):
    require_staff(authorization)
    try:
        return db.list_appointments(date)
    except ValueError as error:
        raise HTTPException(400, "Invalid appointment date.") from error


@app.get("/api/appointments/{appointment_id}/history")
def appointment_history(appointment_id: int, authorization: Optional[str] = Header(default=None)):
    require_staff(authorization)
    appointment = db.get_appointment(appointment_id)
    if not appointment:
        raise HTTPException(404, "Record not found.")
    return db.appointment_history(appointment_id)


@app.post("/api/notifications/retry")
def retry_notifications(authorization: Optional[str] = Header(default=None)):
    require_staff(authorization)
    sent, failed = email_service.send_pending_notifications()
    return {"sent": sent, "pending": failed, "remaining": db.pending_notification_count()}


@app.middleware("http")
async def no_store_patient_responses(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response
