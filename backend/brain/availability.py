"""
Mock availability for the Clinic Appointment Voice Agent.
Generates 4 weeks of Mon–Fri slots from today's date.
No external dependencies.
"""

import sqlite3
import os
from datetime import date, timedelta
from typing import Optional
from .slots import is_time_too_soon

# SQLite Database persistence setup
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "clinic.db")

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            name_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            doctor TEXT NOT NULL,
            date_str TEXT NOT NULL,
            time_str TEXT NOT NULL,
            reason TEXT,
            status TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS booked_slots (
            date_str TEXT NOT NULL,
            time_str TEXT NOT NULL,
            doctor TEXT NOT NULL,
            PRIMARY KEY (date_str, time_str, doctor)
        )
    """)
    conn.commit()
    conn.close()

_init_db()
# "any" in the doctor list means any/no-preference callers are accepted.
MOCK_AVAILABILITY: dict[str, dict[str, list[str]]] = {}


def _build() -> dict[str, dict[str, list[str]]]:
    """Generate availability grid for the next 90 days from today."""
    today = date.today()
    slot_templates = [
        ("09:00", ["any", "Dr. Khan", "Dr. Smith"]),
        ("10:00", ["any", "Dr. Patel"]),
        ("11:00", ["Dr. Khan", "Dr. Ali"]),
        ("14:00", ["any", "Dr. Smith", "Dr. Ali"]),
        ("15:00", ["any", "Dr. Khan"]),
        ("16:00", ["Dr. Patel", "Dr. Smith"]),
    ]
    avail: dict[str, dict[str, list[str]]] = {}
    for offset in range(0, 90):          # 90 days ahead covers upcoming months (e.g. Dec, Jan)
        d = today + timedelta(days=offset)
        avail[d.strftime("%Y-%m-%d")] = {
            t: list(docs) for t, docs in slot_templates
        }
    return avail


MOCK_AVAILABILITY = _build()


def _load_from_db():
    """Load persisted appointments and booked slots from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name_key, name, doctor, date_str, time_str, reason, status FROM appointments")
    for row in cur.fetchall():
        APPOINTMENTS[row[0]] = {
            "name": row[1],
            "doctor": row[2],
            "date": row[3],
            "time": row[4],
            "reason": row[5],
            "status": row[6],
        }
    cur.execute("SELECT date_str, time_str, doctor FROM booked_slots")
    for row in cur.fetchall():
        BOOKED_SLOTS.add((row[0], row[1], row[2]))
    conn.close()

def reset_db():
    """Clear database and in-memory caches (used for tests or clean reset)."""
    APPOINTMENTS.clear()
    BOOKED_SLOTS.clear()
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM appointments")
        cur.execute("DELETE FROM booked_slots")
        conn.commit()
        conn.close()
    except Exception:
        pass

# Active bookings and appointment registry
# APPOINTMENTS: { name_lower: {"name": str, "doctor": str, "date": str, "time": str, "reason": Optional[str], "status": "booked"|"cancelled"} }
# BOOKED_SLOTS: set of (date_str, time_str, doctor_canonical)
APPOINTMENTS: dict[str, dict] = {}
BOOKED_SLOTS: set[tuple[str, str, str]] = set()

_load_from_db()


def is_available(date_str: str, time_str: str, doctor: str) -> bool:
    """Return True if *date_str* / *time_str* / *doctor* is in the mock grid, not too soon today, and not already booked."""
    # Never offer or consider a slot available if it is today and < 1 hour ahead
    if is_time_too_soon(date_str, time_str):
        return False

    slot_doctors = MOCK_AVAILABILITY.get(date_str, {}).get(time_str)
    if slot_doctors is None:
        return False

    # Check if specific doctor is already booked
    if doctor != "any":
        if (date_str, time_str, doctor) in BOOKED_SLOTS:
            return False
        return doctor in slot_doctors or "any" in slot_doctors

    # "any" doctor requested: check if at least one eligible doctor for this slot is unbooked
    eligible_docs = [d for d in slot_doctors if d != "any"]
    if not eligible_docs:
        eligible_docs = ["Dr. Khan", "Dr. Smith", "Dr. Patel", "Dr. Ali"]
    unbooked = [d for d in eligible_docs if (date_str, time_str, d) not in BOOKED_SLOTS]
    return len(unbooked) > 0


def book_slot(name: str, doctor: str, date_str: str, time_str: str, reason: str = "") -> bool:
    """Commit a booking into SQLite and in-memory cache."""
    name_clean = name.strip()
    key = name_clean.lower()
    
    # If "any", assign the first unbooked doctor for that slot
    assigned_doctor = doctor
    if doctor == "any":
        slot_doctors = MOCK_AVAILABILITY.get(date_str, {}).get(time_str, [])
        eligible_docs = [d for d in slot_doctors if d != "any"]
        if not eligible_docs:
            eligible_docs = ["Dr. Khan", "Dr. Smith", "Dr. Patel", "Dr. Ali"]
        for d in eligible_docs:
            if (date_str, time_str, d) not in BOOKED_SLOTS:
                assigned_doctor = d
                break

    BOOKED_SLOTS.add((date_str, time_str, assigned_doctor))
    APPOINTMENTS[key] = {
        "name": name_clean,
        "doctor": assigned_doctor,
        "date": date_str,
        "time": time_str,
        "reason": reason,
        "status": "booked",
    }

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO appointments (name_key, name, doctor, date_str, time_str, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (key, name_clean, assigned_doctor, date_str, time_str, reason, "booked"))
        cur.execute("""
            INSERT OR REPLACE INTO booked_slots (date_str, time_str, doctor)
            VALUES (?, ?, ?)
        """, (date_str, time_str, assigned_doctor))
        conn.commit()
        conn.close()
    except Exception:
        pass

    return True


def cancel_appointment(name: str) -> Optional[dict]:
    """Mark an appointment as cancelled and release the booked slot in DB and memory."""
    key = name.strip().lower()
    appt = APPOINTMENTS.get(key)
    if not appt:
        return None
    
    # Free the slot
    slot_tuple = (appt["date"], appt["time"], appt["doctor"])
    if slot_tuple in BOOKED_SLOTS:
        BOOKED_SLOTS.remove(slot_tuple)

    appt["status"] = "cancelled"

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            UPDATE appointments SET status = 'cancelled' WHERE name_key = ?
        """, (key,))
        cur.execute("""
            DELETE FROM booked_slots WHERE date_str = ? AND time_str = ? AND doctor = ?
        """, (appt["date"], appt["time"], appt["doctor"]))
        conn.commit()
        conn.close()
    except Exception:
        pass

    return appt


def get_appointment(name: str) -> Optional[dict]:
    """Retrieve appointment details by caller name."""
    return APPOINTMENTS.get(name.strip().lower())


def find_alternatives(doctor: str, n: int = 3) -> list[dict]:
    """Return up to *n* available {date, time} dicts for *doctor*."""
    results: list[dict] = []
    for date_str, times in sorted(MOCK_AVAILABILITY.items()):
        for time_str, doctors in sorted(times.items()):
            if is_available(date_str, time_str, doctor):
                results.append({"date": date_str, "time": time_str})
                if len(results) >= n:
                    return results
    return results

