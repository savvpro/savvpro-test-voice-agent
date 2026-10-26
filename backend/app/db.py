import sqlite3
from datetime import date, datetime, time, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS appointments(
  id INTEGER PRIMARY KEY,
  ref TEXT UNIQUE NOT NULL,
  patient_name TEXT NOT NULL,
  dob TEXT NOT NULL,
  doctor_id TEXT NOT NULL,
  start TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'booked' CHECK(status IN ('booked','cancelled')));
CREATE UNIQUE INDEX IF NOT EXISTS one_booking_per_slot
  ON appointments(doctor_id, start) WHERE status='booked';
CREATE TABLE IF NOT EXISTS calls(
  id TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at TEXT NOT NULL);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _weekday_after(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def seed(conn: sqlite3.Connection, today: date) -> None:
    if conn.execute("SELECT 1 FROM appointments LIMIT 1").fetchone():
        return
    d1 = _weekday_after(today)
    d2 = _weekday_after(d1)

    def at(d: date, h: int, m: int = 0) -> str:
        return datetime.combine(d, time(h, m)).isoformat(timespec="minutes")

    rows = [
        ("CLN-JC01", "John Carter", "1985-07-12", "patel", at(d1, 10)),
        ("CLN-ES01", "Emily Stone", "1992-02-29", "nguyen", at(d1, 14)),
        ("CLN-ES02", "Emily Stone", "1992-02-29", "patel", at(d2, 11)),
        ("CLN-AM01", "Alex Morgan", "1970-01-01", "khan", at(d1, 15)),
        ("CLN-AM02", "Alex Morgan", "1970-01-01", "khan", at(d1, 15, 30)),
    ]
    with conn:
        conn.executemany(
            "INSERT INTO appointments(ref, patient_name, dob, doctor_id, start) VALUES (?,?,?,?,?)",
            rows,
        )
