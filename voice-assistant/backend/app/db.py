"""SQLite persistence for appointment tokens, conversations, and audit history."""
from __future__ import annotations

import json
import hashlib
import hmac
import sqlite3
import threading
import secrets
import re
from datetime import date, datetime, timedelta
from typing import Optional

from . import config as C

SCHEMA = """
CREATE TABLE IF NOT EXISTS call_session (
  id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  outcome TEXT,
  state_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS turn (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES call_session(id),
  idx INTEGER NOT NULL,
  user_text TEXT NOT NULL,
  intent TEXT,
  slots_json TEXT,
  state_before TEXT,
  state_after TEXT,
  action TEXT,
  reply TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (session_id, idx)
);
CREATE TABLE IF NOT EXISTS appointment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token INTEGER NOT NULL CHECK (token BETWEEN 1 AND 35),
  appointment_date TEXT NOT NULL,
  start_min INTEGER NOT NULL,
  end_min INTEGER NOT NULL,
  guardian_name TEXT NOT NULL,
  child_name TEXT NOT NULL,
  child_age INTEGER NOT NULL CHECK (child_age BETWEEN 0 AND 18),
  contact TEXT,
  email TEXT,
  email_verified INTEGER NOT NULL DEFAULT 0 CHECK (email_verified IN (0,1)),
  status TEXT NOT NULL CHECK (status IN ('active','cancelled','rescheduled')),
  previous_appointment_id INTEGER REFERENCES appointment(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_appointment_active_token
  ON appointment(appointment_date, token) WHERE status='active';
CREATE INDEX IF NOT EXISTS ix_appointment_date_status
  ON appointment(appointment_date, status);
CREATE TABLE IF NOT EXISTS appointment_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  appointment_id INTEGER NOT NULL REFERENCES appointment(id),
  event TEXT NOT NULL,
  details_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS email_verification (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  email TEXT NOT NULL,
  purpose TEXT NOT NULL,
  code_digest TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  used_at TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_email_verification_session
  ON email_verification(session_id, purpose, created_at);
CREATE TABLE IF NOT EXISTS notification_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  appointment_id INTEGER NOT NULL REFERENCES appointment(id),
  event TEXT NOT NULL CHECK (event IN ('booked','cancelled','rescheduled')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sending','sent')),
  attempts INTEGER NOT NULL DEFAULT 0,
  locked_at TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  sent_at TEXT,
  UNIQUE (appointment_id,event)
);
"""


class AppointmentUnavailable(Exception):
    """Raised when the requested clinic day has no remaining token."""


class SlotChanged(AppointmentUnavailable):
    def __init__(self, token: Optional[int]):
        super().__init__("The proposed token is no longer available.")
        self.token = token


class Database:
    def __init__(self, path: str = C.DB_PATH, now=None):
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.now = now or datetime.now
        with self.lock:
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.execute("PRAGMA busy_timeout=30000")
            self.conn.executescript(SCHEMA)
            columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(appointment)")}
            for name, declaration in (
                ("email", "TEXT"),
                ("email_verified", "INTEGER NOT NULL DEFAULT 0 CHECK (email_verified IN (0,1))"),
            ):
                if name not in columns:
                    self.conn.execute(f"ALTER TABLE appointment ADD COLUMN {name} {declaration}")
            self.conn.commit()

    @staticmethod
    def valid_email(email: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+", email or "")) and len(email) <= 254

    @staticmethod
    def _verification_digest(session_id: str, purpose: str, email: str, salt: str, code: str) -> str:
        material = f"{session_id}:{purpose}:{email.casefold()}:{salt}:{code}".encode()
        return hmac.new(C.EMAIL_VERIFICATION_SECRET.encode(), material, hashlib.sha256).hexdigest()

    def create_email_challenge(self, session_id: str, email: str, purpose: str, code: str):
        if not self.valid_email(email):
            raise ValueError("Please provide a valid email address.")
        salt = secrets.token_hex(16)
        now = self.now()
        digest = self._verification_digest(session_id, purpose, email, salt, code)
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            recent = self.conn.execute(
                """SELECT COUNT(*) AS count FROM email_verification
                   WHERE session_id=? AND created_at>=?""",
                (session_id, (now - timedelta(hours=1)).isoformat(timespec="seconds")),
            ).fetchone()["count"]
            if recent >= 5:
                self.conn.rollback()
                raise ValueError("Too many verification requests. Please try again later.")
            self.conn.execute(
                "UPDATE email_verification SET used_at=? WHERE session_id=? AND purpose=? AND used_at IS NULL",
                (now.isoformat(timespec="seconds"), session_id, purpose),
            )
            self.conn.execute(
                """INSERT INTO email_verification
                   (session_id,email,purpose,code_digest,expires_at,created_at)
                   VALUES (?,?,?,?,?,?)""",
                (session_id, email.casefold(), purpose, f"{salt}:{digest}",
                 (now + timedelta(minutes=10)).isoformat(timespec="seconds"),
                 now.isoformat(timespec="seconds")),
            )
            self.conn.commit()

    def verify_email_challenge(self, session_id: str, email: str, purpose: str, code: str) -> bool:
        now = self.now()
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            row = self.conn.execute(
                """SELECT * FROM email_verification WHERE session_id=? AND email=? AND purpose=?
                   AND used_at IS NULL ORDER BY id DESC LIMIT 1""",
                (session_id, email.casefold(), purpose),
            ).fetchone()
            if not row or row["attempts"] >= 5 or row["expires_at"] < now.isoformat(timespec="seconds"):
                self.conn.rollback()
                return False
            salt, expected = row["code_digest"].split(":", 1)
            supplied = self._verification_digest(session_id, purpose, email, salt, code)
            valid = hmac.compare_digest(expected, supplied)
            if valid:
                self.conn.execute("UPDATE email_verification SET used_at=? WHERE id=?",
                                  (now.isoformat(timespec="seconds"), row["id"]))
            else:
                self.conn.execute("UPDATE email_verification SET attempts=attempts+1 WHERE id=?", (row["id"],))
            self.conn.commit()
            return valid

    def close(self):
        with self.lock:
            self.conn.close()

    def _validate_day(self, date_iso: str) -> date:
        try:
            day = date.fromisoformat(date_iso)
        except (TypeError, ValueError) as exc:
            raise ValueError("Please provide a valid appointment date.") from exc
        if not C.is_working_day(day):
            raise ValueError("The clinic is open Monday through Friday only.")
        if day < self.now().date():
            raise ValueError("Appointments cannot be booked for a past date.")
        return day

    def _active(self, date_iso: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM appointment WHERE appointment_date=? AND status='active' ORDER BY token",
            (date_iso,),
        ).fetchall()
        return [dict(row) for row in rows]

    def schedule(self, date_iso: str) -> dict:
        day = self._validate_day(date_iso)
        with self.lock:
            appointments = self._active(day.isoformat())
            occupied = {item["token"]: item for item in appointments}
            now = self.now()
            slots = []
            for slot in C.generate_slots():
                appointment = occupied.get(slot["token"])
                elapsed = day == now.date() and slot["start_min"] <= now.hour * 60 + now.minute
                slots.append({
                    **slot,
                    "status": "occupied" if appointment else "elapsed" if elapsed else "available",
                })
        return {
            "date": day.isoformat(),
            "capacity": C.DAILY_CAPACITY,
            "active_count": len(appointments),
            "available_count": sum(slot["status"] == "available" for slot in slots),
            "slots": slots,
        }

    def available_appointments(self, date_iso: str) -> list[dict]:
        return [slot for slot in self.schedule(date_iso)["slots"] if slot["status"] == "available"]

    def _next_token(self, date_iso: str) -> Optional[int]:
        occupied = {item["token"] for item in self._active(date_iso)}
        day = date.fromisoformat(date_iso)
        now = self.now()
        current_minute = now.hour * 60 + now.minute
        return next((
            slot["token"] for slot in C.generate_slots()
            if slot["token"] not in occupied
            and (day != now.date() or slot["start_min"] > current_minute)
        ), None)

    def preview(self, date_iso: str) -> Optional[dict]:
        day = self._validate_day(date_iso)
        with self.lock:
            token = self._next_token(day.isoformat())
            return self._appointment_slot(token) if token is not None else None

    @staticmethod
    def _appointment_slot(token: int) -> dict:
        return next(slot for slot in C.generate_slots() if slot["token"] == token)

    def _write_audit(self, appointment_id: int, event: str, details: dict):
        self.conn.execute(
            "INSERT INTO appointment_audit(appointment_id,event,details_json,created_at) VALUES (?,?,?,?)",
            (appointment_id, event, json.dumps(details), self.now().isoformat(timespec="seconds")),
        )

    def _insert(self, token: int, date_iso: str, data: dict,
                previous_appointment_id: Optional[int] = None, event: str = "booked") -> dict:
        if not self.valid_email(data.get("email")) or data.get("email_verified") is not True:
            raise ValueError("A verified guardian email address is required.")
        slot = self._appointment_slot(token)
        timestamp = self.now().isoformat(timespec="seconds")
        cursor = self.conn.execute(
            """INSERT INTO appointment
               (token,appointment_date,start_min,end_min,guardian_name,child_name,child_age,contact,email,email_verified,status,
                previous_appointment_id,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (token, date_iso, slot["start_min"], slot["end_min"], data["guardian_name"],
             data["child_name"], data["child_age"], data.get("contact"), data["email"].casefold(), 1, "active",
             previous_appointment_id, timestamp, timestamp),
        )
        appointment_id = cursor.lastrowid
        self._write_audit(appointment_id, "booked", {"token": token, "date": date_iso})
        self.conn.execute(
            "INSERT INTO notification_outbox(appointment_id,event,created_at) VALUES (?,?,?)",
            (appointment_id, event, timestamp),
        )
        return self.get_appointment(appointment_id)

    def create_appointment(self, date_iso: str, data: dict,
                           expected_token: Optional[int] = None) -> Optional[dict]:
        day = self._validate_day(date_iso)
        if not data.get("guardian_name") or not data.get("child_name"):
            raise ValueError("A parent or guardian name and child's name are required.")
        if not isinstance(data.get("child_age"), int) or not 0 <= data["child_age"] <= 18:
            raise ValueError("Child age must be between 0 and 18.")
        if not self.valid_email(data.get("email")) or data.get("email_verified") is not True:
            raise ValueError("A verified guardian email address is required.")
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                token = self._next_token(day.isoformat())
                if token is None:
                    self.conn.rollback()
                    return None
                if expected_token is not None and token != expected_token:
                    self.conn.rollback()
                    raise SlotChanged(token)
                appointment = self._insert(token, day.isoformat(), data)
                self.conn.commit()
                return appointment
            except Exception:
                self.conn.rollback()
                raise

    def get_appointment(self, appointment_id: int) -> Optional[dict]:
        with self.lock:
            row = self.conn.execute("SELECT * FROM appointment WHERE id=?", (appointment_id,)).fetchone()
            return dict(row) if row else None

    def find_appointment(self, date_iso: str, token: int, verified_email: str) -> Optional[dict]:
        self._validate_day(date_iso)
        if not self.valid_email(verified_email):
            return None
        with self.lock:
            row = self.conn.execute(
                """SELECT * FROM appointment
                   WHERE appointment_date=? AND token=? AND status='active'
                     AND email=? AND email_verified=1""",
                (date_iso, token, verified_email.casefold()),
            ).fetchone()
        return dict(row) if row else None

    def cancel_appointment(self, appointment_id: int) -> bool:
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                row = self.conn.execute(
                    "SELECT * FROM appointment WHERE id=? AND status='active'", (appointment_id,)
                ).fetchone()
                if not row:
                    self.conn.rollback()
                    return False
                self.conn.execute(
                    "UPDATE appointment SET status='cancelled',updated_at=? WHERE id=? AND status='active'",
                    (self.now().isoformat(timespec="seconds"), appointment_id),
                )
                self._write_audit(appointment_id, "cancelled", {"token": row["token"], "date": row["appointment_date"]})
                self.conn.execute(
                    "INSERT INTO notification_outbox(appointment_id,event,created_at) VALUES (?,?,?)",
                    (appointment_id, "cancelled", self.now().isoformat(timespec="seconds")),
                )
                self.conn.commit()
                return True
            except Exception:
                self.conn.rollback()
                raise

    def reschedule_appointment(self, appointment_id: int, new_date: str,
                               expected_token: Optional[int] = None) -> Optional[dict]:
        day = self._validate_day(new_date)
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                old_row = self.conn.execute(
                    "SELECT * FROM appointment WHERE id=? AND status='active'", (appointment_id,)
                ).fetchone()
                if not old_row:
                    self.conn.rollback()
                    return None
                token = self._next_token(day.isoformat())
                if token is None:
                    self.conn.rollback()
                    return None
                if expected_token is not None and token != expected_token:
                    self.conn.rollback()
                    raise SlotChanged(token)
                old = dict(old_row)
                self.conn.execute(
                    "UPDATE appointment SET status='rescheduled',updated_at=? WHERE id=? AND status='active'",
                    (self.now().isoformat(timespec="seconds"), appointment_id),
                )
                self._write_audit(appointment_id, "rescheduled_from", {"to_date": day.isoformat(), "to_token": token})
                result = self._insert(token, day.isoformat(), old,
                                      previous_appointment_id=appointment_id, event="rescheduled")
                self.conn.commit()
                return result
            except Exception:
                self.conn.rollback()
                raise

    def list_appointments(self, date_iso: Optional[str] = None) -> list[dict]:
        query = "SELECT * FROM appointment"
        parameters: tuple = ()
        if date_iso:
            try:
                date.fromisoformat(date_iso)
            except ValueError as error:
                raise ValueError("Please provide a valid appointment date.") from error
            query += " WHERE appointment_date=?"
            parameters = (date_iso,)
        query += " ORDER BY appointment_date,token,id"
        with self.lock:
            return [dict(row) for row in self.conn.execute(query, parameters).fetchall()]

    def appointment_history(self, appointment_id: int) -> list[dict]:
        with self.lock:
            return [dict(row) for row in self.conn.execute(
                "SELECT * FROM appointment_audit WHERE appointment_id=? ORDER BY id", (appointment_id,)
            ).fetchall()]

    def claim_notifications(self, limit: int = 20) -> list[dict]:
        now = self.now()
        stale_before = (now - timedelta(minutes=5)).isoformat(timespec="seconds")
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            rows = self.conn.execute(
                """SELECT n.id AS notification_id,n.event,a.id,a.email,a.email_verified,a.child_name,
                          a.guardian_name,a.token,a.appointment_date,a.start_min,a.status
                   FROM notification_outbox n JOIN appointment a ON a.id=n.appointment_id
                   WHERE a.email_verified=1 AND a.email IS NOT NULL AND n.attempts<10
                     AND (n.status='pending' OR (n.status='sending' AND n.locked_at<?))
                   ORDER BY n.id LIMIT ?""",
                (stale_before, limit),
            ).fetchall()
            claimed = []
            for row in rows:
                changed = self.conn.execute(
                    """UPDATE notification_outbox SET status='sending',locked_at=?,attempts=attempts+1
                       WHERE id=? AND (status='pending' OR (status='sending' AND locked_at<?))""",
                    (now.isoformat(timespec="seconds"), row["notification_id"], stale_before),
                ).rowcount
                if changed:
                    claimed.append(dict(row))
            self.conn.commit()
            return claimed

    def finish_notification(self, notification_id: int, delivered: bool):
        with self.lock:
            if delivered:
                self.conn.execute(
                    """UPDATE notification_outbox SET status='sent',sent_at=?,locked_at=NULL,last_error=NULL
                       WHERE id=? AND status='sending'""",
                    (self.now().isoformat(timespec="seconds"), notification_id),
                )
            else:
                self.conn.execute(
                    """UPDATE notification_outbox SET status='pending',locked_at=NULL,last_error='delivery failed'
                       WHERE id=? AND status='sending'""",
                    (notification_id,),
                )
            self.conn.commit()

    def notification_status(self, appointment_id: int, event: str) -> Optional[str]:
        with self.lock:
            row = self.conn.execute(
                "SELECT status FROM notification_outbox WHERE appointment_id=? AND event=?",
                (appointment_id, event),
            ).fetchone()
            return row["status"] if row else None

    def pending_notification_count(self) -> int:
        with self.lock:
            row = self.conn.execute(
                "SELECT COUNT(*) AS count FROM notification_outbox WHERE status!='sent'"
            ).fetchone()
            return row["count"]

    def start_session(self, sid: str, state_json: str):
        with self.lock:
            self.conn.execute("INSERT INTO call_session(id,started_at,state_json) VALUES (?,?,?)",
                              (sid, self.now().isoformat(timespec="seconds"), state_json))
            self.conn.commit()

    def load_state(self, sid: str) -> Optional[str]:
        with self.lock:
            row = self.conn.execute("SELECT state_json FROM call_session WHERE id=?", (sid,)).fetchone()
            return row["state_json"] if row else None

    def save_state(self, sid: str, state_json: str, ended: bool = False, outcome: Optional[str] = None):
        with self.lock:
            self.conn.execute(
                """UPDATE call_session SET state_json=?,
                   ended_at=CASE WHEN ? THEN ? ELSE ended_at END,
                   outcome=COALESCE(?,outcome) WHERE id=?""",
                (state_json, int(ended), self.now().isoformat(timespec="seconds"), outcome, sid),
            )
            self.conn.commit()

    def log_turn(self, sid: str, idx: int, user_text: str, intent: str, slots: dict,
                 before: str, after: str, action: str, reply: str):
        with self.lock:
            self.conn.execute(
                """INSERT INTO turn(session_id,idx,user_text,intent,slots_json,state_before,state_after,action,reply,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (sid, idx, "[redacted]", intent, "{}", before, after, action, "[redacted]",
                 self.now().isoformat(timespec="seconds")),
            )
            self.conn.commit()

    def transcript(self, sid: str) -> list[dict]:
        with self.lock:
            return [dict(row) for row in self.conn.execute(
                "SELECT * FROM turn WHERE session_id=? ORDER BY idx", (sid,)
            ).fetchall()]
