import secrets
import sqlite3
import string
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum

from app.clinic import CLOSE, OPEN, SLOT_MINUTES

_REF_CHARS = string.ascii_uppercase + string.digits


@dataclass(frozen=True)
class Appointment:
    ref: str
    patient_name: str
    dob: date
    doctor_id: str
    start: datetime


class SlotProblem(StrEnum):
    PAST = "past"
    WEEKEND = "weekend"
    CLOSED = "closed"
    OFF_GRID = "off_grid"


class SlotTaken(Exception):
    pass


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="minutes")


def check_slot(start: datetime, now: datetime) -> SlotProblem | None:
    if start < now:
        return SlotProblem.PAST
    if start.weekday() >= 5:
        return SlotProblem.WEEKEND
    if not OPEN <= start.time() < CLOSE:
        return SlotProblem.CLOSED
    if start.minute % SLOT_MINUTES or start.second:
        return SlotProblem.OFF_GRID
    return None


def is_free(conn: sqlite3.Connection, doctor_id: str, start: datetime) -> bool:
    row = conn.execute(
        "SELECT 1 FROM appointments WHERE doctor_id=? AND start=? AND status='booked'",
        (doctor_id, _iso(start)),
    ).fetchone()
    return row is None


def nearest_free(
    conn: sqlite3.Connection,
    doctor_ids: list[str],
    near: datetime,
    now: datetime,
    limit: int = 3,
) -> list[tuple[str, datetime]]:
    if not doctor_ids:
        return []
    first = near.date() - timedelta(days=14)
    last = near.date() + timedelta(days=14)
    lo = _iso(datetime.combine(first, time.min))
    hi = _iso(datetime.combine(last + timedelta(days=1), time.min))
    marks = ",".join("?" * len(doctor_ids))
    booked = {
        (r["doctor_id"], r["start"])
        for r in conn.execute(
            "SELECT doctor_id, start FROM appointments WHERE status='booked'"
            f" AND doctor_id IN ({marks}) AND start >= ? AND start < ?",
            (*doctor_ids, lo, hi),
        )
    }
    found: list[tuple[timedelta, datetime, int, str]] = []
    for i in range((last - first).days + 1):
        t = datetime.combine(first + timedelta(days=i), OPEN)
        while t.time() < CLOSE:
            if check_slot(t, now) is None:
                for order, d in enumerate(doctor_ids):
                    if (d, _iso(t)) not in booked:
                        found.append((abs(t - near), t, order, d))
                        break  # one entry per start time
            t += timedelta(minutes=SLOT_MINUTES)
    found.sort(key=lambda x: x[:3])
    return [(d, t) for _, t, _, d in found[:limit]]


def _new_ref(conn: sqlite3.Connection) -> str:
    while True:
        ref = "CLN-" + "".join(secrets.choice(_REF_CHARS) for _ in range(4))
        if not conn.execute("SELECT 1 FROM appointments WHERE ref=?", (ref,)).fetchone():
            return ref


def _to_appt(r: sqlite3.Row) -> Appointment:
    return Appointment(
        r["ref"],
        r["patient_name"],
        date.fromisoformat(r["dob"]),
        r["doctor_id"],
        datetime.fromisoformat(r["start"]),
    )


def book(
    conn: sqlite3.Connection, name: str, dob: date, doctor_id: str, start: datetime
) -> Appointment:
    ref = _new_ref(conn)
    try:
        with conn:
            conn.execute(
                "INSERT INTO appointments(ref, patient_name, dob, doctor_id, start)"
                " VALUES (?,?,?,?,?)",
                (ref, name.strip(), dob.isoformat(), doctor_id, _iso(start)),
            )
    except sqlite3.IntegrityError as e:
        raise SlotTaken(f"{doctor_id} at {_iso(start)} is taken") from e
    return Appointment(ref, name.strip(), dob, doctor_id, start)


def find_upcoming(
    conn: sqlite3.Connection,
    now: datetime,
    *,
    ref: str | None = None,
    name: str | None = None,
    dob: date | None = None,
) -> list[Appointment]:
    sql = "SELECT * FROM appointments WHERE status='booked' AND start >= ?"
    args: list[str] = [_iso(now)]
    if ref is not None:
        sql += " AND ref=?"
        args.append(ref.strip().upper())
    elif name is not None and dob is not None:
        sql += " AND lower(patient_name)=? AND dob=?"
        args += [name.strip().lower(), dob.isoformat()]
    else:
        return []
    return [_to_appt(r) for r in conn.execute(sql + " ORDER BY start", args)]


def cancel(conn: sqlite3.Connection, ref: str) -> None:
    with conn:
        conn.execute("UPDATE appointments SET status='cancelled' WHERE ref=?", (ref,))


def reschedule(
    conn: sqlite3.Connection, ref: str, new_start: datetime, doctor_id: str
) -> Appointment:
    try:
        with conn:
            cur = conn.execute(
                "UPDATE appointments SET doctor_id=?, start=? WHERE ref=? AND status='booked'",
                (doctor_id, _iso(new_start), ref),
            )
            if cur.rowcount != 1:
                raise KeyError(ref)
    except sqlite3.IntegrityError as e:
        raise SlotTaken(f"{doctor_id} at {_iso(new_start)} is taken") from e
    return _to_appt(conn.execute("SELECT * FROM appointments WHERE ref=?", (ref,)).fetchone())
