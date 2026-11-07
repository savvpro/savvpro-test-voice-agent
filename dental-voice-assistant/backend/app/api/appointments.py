"""Appointments REST API.

Routes
------
GET  /appointments/slots?date=YYYY-MM-DD     free slots for a day
GET  /appointments?date=YYYY-MM-DD           booked appointments for a day
POST /appointments                           book a new appointment
GET  /appointments/by-phone?phone=...        upcoming by phone
DELETE /appointments/{id}                    cancel
PUT  /appointments/{id}/reschedule           reschedule
"""

from __future__ import annotations

import logging
from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.models import Appointment
from app.logging_config import mask_phone
from app.repositories import appointments as repo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/appointments", tags=["appointments"])


# ── Request / Response schemas ────────────────────────────────────────────────


class SlotSchema(BaseModel):
    date: date
    start_time: time
    end_time: time


class AppointmentIn(BaseModel):
    patient_name: str
    patient_phone: str
    service: str
    date: date
    start_time: time
    end_time: time


class AppointmentOut(BaseModel):
    id: str
    patient_name: str
    patient_phone: str
    service: str
    appointment_date: date
    start_time: time
    end_time: time
    status: str

    model_config = {"from_attributes": True}


class RescheduleIn(BaseModel):
    new_date: date
    new_start_time: time
    new_end_time: time


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/slots", response_model=list[SlotSchema], summary="Free slots for a day")
async def free_slots(
    day: date = Query(..., alias="date"),
    session: AsyncSession = Depends(get_session),
) -> list[SlotSchema]:
    slots = await repo.free_slots(session, day)
    return [SlotSchema(date=day, start_time=s, end_time=e) for s, e in slots]


@router.get("", response_model=list[AppointmentOut], summary="Appointments for a day")
async def list_by_day(
    day: date = Query(..., alias="date"),
    session: AsyncSession = Depends(get_session),
) -> list[AppointmentOut]:
    appts = await repo.list_by_day(session, day)
    return [AppointmentOut.model_validate(a) for a in appts]


@router.post("", response_model=AppointmentOut, status_code=201, summary="Book appointment")
async def book(
    body: AppointmentIn,
    session: AsyncSession = Depends(get_session),
) -> AppointmentOut:
    appt = Appointment(
        patient_name=body.patient_name,
        patient_phone=body.patient_phone,
        service=body.service,
        appointment_date=body.date,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    result = await repo.create(session, appt)
    if result is None:
        raise HTTPException(status_code=409, detail="Slot already booked.")
    logger.info(
        "appointment_booked",
        extra={"id": result.id, "phone": mask_phone(body.patient_phone)},
    )
    return AppointmentOut.model_validate(result)


@router.get("/by-phone", response_model=list[AppointmentOut], summary="Upcoming by phone")
async def by_phone(
    phone: str = Query(..., min_length=7, max_length=15),
    session: AsyncSession = Depends(get_session),
) -> list[AppointmentOut]:
    appts = await repo.find_upcoming_by_phone(session, phone)
    return [AppointmentOut.model_validate(a) for a in appts]


@router.delete("/{appointment_id}", status_code=204, summary="Cancel appointment")
async def cancel(
    appointment_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    ok = await repo.cancel(session, appointment_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Appointment not found or already cancelled.")
    logger.info("appointment_cancelled", extra={"id": appointment_id})


@router.put(
    "/{appointment_id}/reschedule",
    response_model=AppointmentOut,
    summary="Reschedule appointment",
)
async def reschedule(
    appointment_id: str,
    body: RescheduleIn,
    session: AsyncSession = Depends(get_session),
) -> AppointmentOut:
    # We need the old appointment's patient info to carry forward
    from sqlalchemy import select as sa_select

    result = await session.execute(sa_select(Appointment).where(Appointment.id == appointment_id))
    old = result.scalar_one_or_none()
    if old is None:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    new_appt = Appointment(
        patient_name=old.patient_name,
        patient_phone=old.patient_phone,
        service=old.service,
        appointment_date=body.new_date,
        start_time=body.new_start_time,
        end_time=body.new_end_time,
    )
    updated = await repo.reschedule(session, appointment_id, new_appt)
    if updated is None:
        raise HTTPException(status_code=409, detail="New slot already booked.")
    logger.info(
        "appointment_rescheduled",
        extra={"old_id": appointment_id, "new_id": updated.id},
    )
    return AppointmentOut.model_validate(updated)
