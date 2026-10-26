"""Read-only views of the clinic database for the UI side panel."""

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_conversation, get_db
from app.db import repository
from app.schemas import AppointmentOut, SlotOut, mask_phone
from app.services.conversation import ConversationService

router = APIRouter(prefix="/api/admin", tags=["admin"])

Db = Annotated[Session, Depends(get_db)]


@router.get("/slots")
def list_slots(db: Db, department: str | None = None, date: dt.date | None = None) -> list[SlotOut]:
    return [
        SlotOut(
            id=s.id,
            start=s.start_time,
            end=s.end_time,
            doctor=s.doctor.name,
            department=s.doctor.department.name,
            is_booked=s.is_booked,
        )
        for s in repository.list_slots(db, department=department, day=date)
    ]


@router.get("/appointments")
def list_appointments(
    db: Db,
    conversation: Annotated[ConversationService, Depends(get_conversation)],
    order: Literal["start", "recent"] = "start",
) -> list[AppointmentOut]:
    """Upcoming bookings, soonest first; ``order=recent`` puts the newest bookings first."""
    return [
        AppointmentOut(
            booking_ref=a.booking_ref,
            patient_name=a.patient.name,
            phone=mask_phone(a.patient.phone),
            start=a.slot.start_time,
            doctor=a.slot.doctor.name,
            department=a.slot.doctor.department.name,
            status=a.status.value,
        )
        for a in repository.list_upcoming_appointments(
            db, now=conversation.now(), newest_first=order == "recent"
        )
    ]
