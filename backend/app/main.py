import json
import os
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .brain import TZ, WELCOME, advance, clock, initial, quote
from .store import Store

app = FastAPI(title="Mezban", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
store = Store(os.environ.get("MEZBAN_DB", "mezban.db"))


class Turn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(min_length=1, max_length=100)

    @field_validator("text", "request_id")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Must not be blank")
        return value.strip()


class Lookup(BaseModel):
    reference: str = Field(min_length=3, max_length=30)
    phone: str = Field(pattern=r"^03\d{9}$")


def response(sid, state, message):
    fields = state["fields"]
    return {
        "session_id": sid,
        "state": state,
        "message": message,
        "quote": quote(fields)
        if fields.get("adults") is not None and fields.get("children") is not None
        else None,
    }


def load(db, sid):
    row = db.execute("SELECT state FROM sessions WHERE id=?", (sid,)).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    return json.loads(row[0])


def save(db, sid, state):
    db.execute("UPDATE sessions SET state=? WHERE id=?", (json.dumps(state), sid))


@app.get("/api/health")
def health():
    return {"status": "ok", "brain": "deterministic-python"}


@app.post("/api/sessions")
def session():
    sid = uuid.uuid4().hex
    state = initial()
    with store.connection() as db:
        db.execute("INSERT INTO sessions VALUES(?,?)", (sid, json.dumps(state)))
    return response(sid, state, WELCOME)


@app.post("/api/bookings/lookup")
def lookup(payload: Lookup):
    with store.connection() as db:
        store.expire(db, datetime.now(TZ))
        row = db.execute(
            "SELECT * FROM bookings WHERE id=?", (payload.reference.upper(),)
        ).fetchone()
        if not row or json.loads(row["fields"])["phone"] != payload.phone:
            raise HTTPException(404, "No matching demo reservation")
        if row["status"] not in ["confirmed", "payment_pending"]:
            raise HTTPException(409, "This reservation is no longer active")
        state = load(db, row["session_id"])
        state["fields"] = json.loads(row["fields"])
        state["booking"] = {
            "id": row["id"],
            "status": row["status"],
            "expires": row["expires"],
            "quote": quote(state["fields"]),
        }
        state["stage"] = row["status"]
        state["awaiting"] = None
        state["rule"] = "booking_verified"
        save(db, row["session_id"], state)
        return response(
            row["session_id"],
            state,
            f"Found {row['id']}. Tell me what to change, or say cancel to cancel this reservation.",
        )


@app.post("/api/sessions/{sid}/turns")
def turn(sid: str, payload: Turn):
    with store.connection() as db:
        state = load(db, sid)
        previous = db.execute(
            "SELECT response FROM turns WHERE session_id=? AND request_id=?",
            (sid, payload.request_id),
        ).fetchone()
        if previous:
            cached = json.loads(previous[0])
            if cached.get("request_text") != payload.text:
                raise HTTPException(
                    409, "Request ID was already used for a different message"
                )
            cached.pop("request_text", None)
            return cached
        now = datetime.now(TZ)
        store.expire(db, now)
        if state.get("booking"):
            row = db.execute(
                "SELECT status FROM bookings WHERE id=?", (state["booking"]["id"],)
            ).fetchone()
            state["booking"]["status"] = row[0]
        message = advance(state, payload.text, now)
        state["alternatives"] = []
        if state["intent"] == "REQUEST_STAFF":
            db.execute(
                "INSERT INTO assistance VALUES(?,?,?)",
                (uuid.uuid4().hex, sid, payload.text),
            )
        if message == "BOOK_ACTION":
            booking = store.book(db, sid, state, now)
            if booking:
                state["booking"] = booking
                state["stage"] = booking["status"]
                message = f"Reference {booking['id']}. " + (
                    "Your table is held for 10 minutes pending the simulated deposit. Use Simulate deposit to confirm."
                    if booking["status"] == "payment_pending"
                    else "Your table is confirmed. Thank you, Allah hafiz!"
                )
            else:
                options = store.alternatives(db, state, now)
                state["stage"] = "collecting"
                state["awaiting"] = "time"
                state["rule"] = "capacity_unavailable"
                state["alternatives"] = options
                state["fields"].pop("time", None)
                suggestions = ", ".join(
                    f"{clock(o['time'])} {o['seating']}" for o in options
                )
                message = (
                    "That seating area is full. Your previous reservation, if any, is kept. "
                    + (
                        f"Available alternatives: {suggestions}. Which would you like?"
                        if suggestions
                        else "No tables fit that date. Please choose another date."
                    )
                )
        elif message == "CANCEL_ACTION":
            db.execute(
                "UPDATE bookings SET status='cancelled' WHERE id=? AND session_id=?",
                (state["booking"]["id"], sid),
            )
            state["booking"]["status"] = "cancelled"
            state["stage"] = "ended"
            message = (
                "Reservation cancelled. This demo moves no real money. Allah hafiz!"
            )
        save(db, sid, state)
        result = response(sid, state, message)
        db.execute(
            "INSERT INTO turns VALUES(?,?,?)",
            (
                sid,
                payload.request_id,
                json.dumps(dict(result, request_text=payload.text)),
            ),
        )
        return result


@app.post("/api/sessions/{sid}/demo-payment")
def pay(sid: str):
    with store.connection() as db:
        state = load(db, sid)
        store.expire(db, datetime.now(TZ))
        if not state.get("booking"):
            raise HTTPException(409, "No booking to pay for")
        row = db.execute(
            "SELECT status FROM bookings WHERE id=? AND session_id=?",
            (state["booking"]["id"], sid),
        ).fetchone()
        if row[0] not in ["payment_pending", "confirmed"]:
            raise HTTPException(
                409, "Hold expired or booking inactive. Start a new booking."
            )
        db.execute(
            "UPDATE bookings SET status='confirmed', expires=NULL WHERE id=?",
            (state["booking"]["id"],),
        )
        state["booking"].update(status="confirmed", expires=None)
        state["stage"] = "confirmed"
        state["rule"] = "demo_payment_verified"
        save(db, sid, state)
        return response(
            sid,
            state,
            f"Demo deposit verified. Booking {state['booking']['id']} is confirmed. Allah hafiz!",
        )
