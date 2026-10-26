from datetime import datetime, time, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import Allocation, Appointment, Bay, CallerSession, ProcessedTurn
from backend.domain import SERVICES, describe, from_utc, next_open, utc_naive, validate_slot


def owned(db: Session, sid: str, now: datetime) -> list[Appointment]:
    return list(
        db.scalars(
            select(Appointment)
            .where(
                Appointment.session_id == sid,
                Appointment.kind == "caller",
                Appointment.status == "active",
                Appointment.start > utc_naive(now),
            )
            .order_by(Appointment.start, Appointment.id)
        )
    )


def summary(appt: Appointment) -> dict[str, Any]:
    start = from_utc(appt.start)
    return {
        "id": appt.id,
        "reference": appt.id[:8].upper(),
        "service": appt.service,
        "service_name": SERVICES[appt.service]["name"],
        "vehicle": appt.vehicle,
        "date": start.date().isoformat(),
        "time": start.strftime("%H:%M"),
        "description": describe(appt.service, appt.vehicle, start),
        "minutes": SERVICES[appt.service]["minutes"],
        "status": appt.status,
    }


def segments(start: datetime, service: str) -> list[datetime]:
    return [
        utc_naive(start + timedelta(minutes=offset))
        for offset in range(0, SERVICES[service]["minutes"], 30)
    ]


def free_bays(
    db: Session, sid: str, start: datetime, service: str, exclude: str | None = None
) -> list[Bay]:
    busy = select(Allocation.bay_id).where(Allocation.segment_start.in_(segments(start, service)))
    if exclude:
        busy = busy.where(Allocation.appointment_id != exclude)
    return list(
        db.scalars(
            select(Bay).where(Bay.session_id == sid, Bay.id.not_in(busy)).order_by(Bay.number)
        )
    )


def reserve(
    db: Session,
    sid: str,
    service: str,
    vehicle: str,
    start: datetime,
    existing: Appointment | None = None,
) -> Appointment | None:
    for bay in free_bays(db, sid, start, service, existing.id if existing else None):
        try:
            with db.begin_nested():
                if existing:
                    db.execute(delete(Allocation).where(Allocation.appointment_id == existing.id))
                    appt = existing
                    appt.start, appt.service, appt.vehicle = utc_naive(start), service, vehicle
                else:
                    appt = Appointment(
                        id=str(uuid4()),
                        session_id=sid,
                        service=service,
                        vehicle=vehicle,
                        start=utc_naive(start),
                        kind="caller",
                    )
                    db.add(appt)
                    db.flush()
                db.add_all(
                    [
                        Allocation(bay_id=bay.id, appointment_id=appt.id, segment_start=stamp)
                        for stamp in segments(start, service)
                    ]
                )
                db.flush()
            return appt
        except IntegrityError:
            # Another transaction won this bay. The savepoint restores the old booking.
            continue
    return None


def alternatives(
    db: Session,
    sid: str,
    requested: datetime,
    service: str,
    now: datetime,
    exclude: str | None = None,
) -> list[dict[str, str]]:
    choices: list[tuple[float, datetime]] = []
    for offset in range(15):
        day = now.date() + timedelta(days=offset)
        for minute in range(9 * 60, 18 * 60, 30):
            start = datetime.combine(day, time(minute // 60, minute % 60), now.tzinfo)
            if validate_slot(service, start, now) is None:
                choices.append((abs((start - requested).total_seconds()), start))
    result: list[dict[str, str]] = []
    for _, start in sorted(choices, key=lambda pair: (pair[0], pair[1])):
        if free_bays(db, sid, start, service, exclude):
            result.append(
                {
                    "date": start.date().isoformat(),
                    "time": start.strftime("%H:%M"),
                    "label": start.strftime("%a %d %b, %I:%M %p").replace(" 0", " ") + " PKT",
                }
            )
        if len(result) == 3:
            break
    return result


def seed(db: Session, caller: CallerSession, now: datetime) -> None:
    if db.scalar(select(Bay.id).where(Bay.session_id == caller.id).limit(1)):
        return
    bays = [Bay(id=str(uuid4()), session_id=caller.id, number=n) for n in (1, 2)]
    db.add_all(bays)
    db.flush()
    for offset in range(1, 4):
        day = now.date() + timedelta(days=offset)
        if day.weekday() == 6:
            continue
        for bay in bays:
            for hour, minute in ((14, 0), (14, 30), (17, 30)):
                start = datetime.combine(day, time(hour, minute), now.tzinfo)
                appt = Appointment(
                    id=str(uuid4()),
                    session_id=caller.id,
                    service="oil_change",
                    vehicle="car",
                    start=utc_naive(start),
                    kind="background",
                )
                db.add(appt)
                db.flush()
                db.add(
                    Allocation(
                        bay_id=bay.id, appointment_id=appt.id, segment_start=utc_naive(start)
                    )
                )
    day = next_open(now.date() + timedelta(days=1))
    assert (
        reserve(db, caller.id, "tyre_rotation", "suv", datetime.combine(day, time(11), now.tzinfo))
        is not None
    )


def reset(db: Session, caller: CallerSession, now: datetime) -> None:
    appts = select(Appointment.id).where(Appointment.session_id == caller.id)
    db.execute(delete(Allocation).where(Allocation.appointment_id.in_(appts)))
    db.execute(delete(Appointment).where(Appointment.session_id == caller.id))
    db.execute(delete(Bay).where(Bay.session_id == caller.id))
    db.execute(delete(ProcessedTurn).where(ProcessedTurn.session_id == caller.id))
    caller.state = {}
    seed(db, caller, now)
