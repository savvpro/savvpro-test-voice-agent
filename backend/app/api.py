from dataclasses import asdict
from datetime import date, datetime
from typing import Callable
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bookings import Bookings
from app.brain.engine import BookingError, Engine
from app.catalog import BUSINESS_INFO, SERVICES
from app.config import Settings
from app.db import Conversation, Database, Receipt
from app.schemas import AppointmentView, Entities, Message, SessionView, TurnRequest


def router(database: Database, settings: Settings, clock: Callable[[], datetime]) -> APIRouter:
    routes = APIRouter(prefix="/api")

    @routes.get("/health")
    def health():
        with Session(database.engine) as db:
            db.execute(select(1))
        return {"status": "ok", "brain": "deterministic-python", "timezone": settings.business_timezone}

    @routes.get("/business")
    def business():
        return {"name": "Northline Studio", "timezone": settings.business_timezone,
                "description": BUSINESS_INFO, "services": [asdict(s) for s in SERVICES.values()],
                "hours": "Monday–Saturday, 10:00–19:00", "currency": "PKR"}

    @routes.post("/sessions", response_model=SessionView, status_code=201)
    def create_session():
        context = SessionView(id=str(uuid4()))
        context.history.append(Message(role="assistant", text=context.reply))
        with database.transaction() as db:
            db.add(Conversation(id=context.id, payload=context.model_dump(mode="json")))
        return context

    @routes.get("/sessions/{session_id}", response_model=SessionView)
    def get_session(session_id: str):
        with Session(database.engine) as db:
            row = db.get(Conversation, session_id)
            if row is None:
                raise HTTPException(404, "Conversation not found. Start a new session.")
            return SessionView.model_validate(row.payload)

    @routes.post("/sessions/{session_id}/turns", response_model=SessionView)
    def submit_turn(session_id: str, request: TurnRequest):
        with database.transaction() as db:
            row = db.get(Conversation, session_id)
            if row is None:
                raise HTTPException(404, "Conversation not found. Start a new session.")
            receipt = db.scalar(select(Receipt).where(Receipt.session_id == session_id, Receipt.request_id == request.request_id))
            if receipt:
                if receipt.request_text != request.text or receipt.expected_revision != request.expected_revision:
                    raise HTTPException(409, "This request ID was already used with different content.")
                return SessionView.model_validate(receipt.response)
            context = SessionView.model_validate(row.payload)
            if request.expected_revision != context.revision:
                raise HTTPException(409, "This conversation changed. Refresh its state before sending another turn.")
            now = clock()
            engine = Engine(Bookings(db, settings, now), now.astimezone(settings.zone))
            result = engine.turn(context, request.text)
            row.payload = result.model_dump(mode="json")
            db.add(Receipt(session_id=session_id, request_id=request.request_id,
                           request_text=request.text, expected_revision=request.expected_revision,
                           response=row.payload))
        return result

    @routes.get("/availability")
    def availability(service: str, day: date, period: str | None = Query(default=None, pattern="^(morning|afternoon|evening)$")):
        with Session(database.engine) as db:
            try:
                slots = Bookings(db, settings, clock()).slots(Entities(service=service, date=day.isoformat(), period=period))
            except BookingError as error:
                raise HTTPException(422, str(error))
        return {"service": service, "date": day.isoformat(), "timezone": settings.business_timezone, "slots": slots}

    @routes.get("/appointments/{reference}", response_model=AppointmentView)
    def appointment(reference: str):
        with Session(database.engine) as db:
            try:
                return Bookings(db, settings, clock()).lookup(reference)
            except BookingError as error:
                raise HTTPException(404, str(error))

    return routes
