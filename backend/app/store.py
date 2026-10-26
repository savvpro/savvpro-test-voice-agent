"""SQLite writes use BEGIN IMMEDIATE to serialize capacity checks and commits."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta

from .brain import TZ, quote


class Store:
    def __init__(self, path):
        self.path = path
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, state TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS bookings(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, fields TEXT NOT NULL, day TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL, seats INTEGER NOT NULL, area TEXT NOT NULL, status TEXT NOT NULL, expires TEXT);
                CREATE TABLE IF NOT EXISTS turns(session_id TEXT NOT NULL, request_id TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(session_id, request_id));
                CREATE TABLE IF NOT EXISTS assistance(id TEXT PRIMARY KEY, session_id TEXT, message TEXT);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def expire(self, db, now):
        db.execute(
            "UPDATE bookings SET status='expired' WHERE status='payment_pending' AND expires <= ?",
            (now.isoformat(),),
        )

    def can_fit(self, db, fields, old_id=""):
        duration = 90 if fields["dining"] == "hi-tea" else 120
        rows = db.execute(
            "SELECT seats FROM bookings WHERE day=? AND area=? AND status IN ('confirmed','payment_pending') AND start < ? AND end > ? AND id != ?",
            (
                fields["date"],
                fields["seating"],
                fields["time"] + duration,
                fields["time"],
                old_id,
            ),
        ).fetchall()
        needed = (fields["adults"] + len(fields["children"]) + 3) // 4
        return sum((r["seats"] + 3) // 4 for r in rows) + needed <= 3

    def alternatives(self, db, state, now):
        from .brain import SLOTS

        fields = state["fields"]
        old_id = (state.get("booking") or {}).get("id", "")
        times = SLOTS.get(fields["dining"], list(range(720, 1261, 30)))
        options = []
        for minute in sorted(times, key=lambda t: abs(t - fields["time"])):
            for area in [
                fields["seating"],
                "rooftop" if fields["seating"] == "indoor" else "indoor",
            ]:
                candidate = dict(fields, time=minute, seating=area)
                arrival = datetime.fromisoformat(fields["date"]).replace(
                    hour=minute // 60, minute=minute % 60, tzinfo=TZ
                )
                if arrival > now and self.can_fit(db, candidate, old_id):
                    options.append({"time": minute, "seating": area})
                if len(options) == 3:
                    return options
        return options

    def book(self, db, session_id, state, now):
        self.expire(db, now)
        f = state["fields"]
        old = state.get("booking")
        # Each area has three joinable four-seat tables. Round each reservation up
        # to whole tables, including free children; both dining modes share inventory.
        duration = 90 if f["dining"] == "hi-tea" else 120
        if not self.can_fit(db, f, old["id"] if old else ""):
            return None
        amount = quote(f)
        status = "payment_pending" if amount else "confirmed"
        ref = "MZ-" + uuid.uuid4().hex[:8].upper()
        expires = (now + timedelta(minutes=10)).isoformat() if amount else None
        db.execute(
            "INSERT INTO bookings VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                ref,
                session_id,
                json.dumps(f),
                f["date"],
                f["time"],
                f["time"] + duration,
                f["adults"] + len(f["children"]),
                f["seating"],
                status,
                expires,
            ),
        )
        if old:
            db.execute(
                "UPDATE bookings SET status='replaced' WHERE id=? AND session_id=?",
                (old["id"], session_id),
            )
        return {"id": ref, "status": status, "expires": expires, "quote": amount}
