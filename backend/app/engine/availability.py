"""Fake restaurant tables + SQLite-backed bookings for Harbor Lights Bistro."""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from app.db import connect, db_path, init_db

# Dinner service slots (fake restaurant hours)
SERVICE_TIMES = [
    "17:00",
    "17:30",
    "18:00",
    "18:30",
    "19:00",
    "19:30",
    "20:00",
    "20:30",
    "21:00",
]

# Tables: label -> max seats
TABLES = {
    "T1": 2,
    "T2": 2,
    "T3": 4,
    "T4": 4,
    "T5": 6,
    "T6": 6,
    "T7": 8,
    "T8": 10,
}


@dataclass
class BookingRecord:
    id: str
    date: str
    time: str
    party_size: int
    table_label: str
    guest_name: Optional[str] = None
    restaurant: str = "Harbor Lights Bistro"
    status: str = "active"
    created_at: Optional[str] = None


def _row_to_record(r) -> BookingRecord:
    return BookingRecord(
        id=r["id"],
        restaurant=r["restaurant"],
        date=r["date"],
        time=r["time"],
        party_size=r["party_size"],
        table_label=r["table_label"],
        guest_name=r["guest_name"],
        status=r["status"] if "status" in r.keys() else "active",
        created_at=r["created_at"],
    )


class AvailabilityStore:
    """Tracks booked tables in SQLite. Fake tables / hours stay in code."""

    def __init__(self, path=None) -> None:
        self._path = path  # None → use BOOKINGS_DB / default
        init_db(self._path)

    def _conn(self):
        return connect(self._path)

    def _taken_tables(self, date_: str, time: str) -> set[str]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT table_label FROM bookings
                WHERE date = ? AND time = ? AND status = 'active'
                """,
                (date_, time),
            ).fetchall()
            return {r["table_label"] for r in rows}
        finally:
            conn.close()

    def find_table(self, date_: str, time: str, party_size: int) -> Optional[str]:
        if time not in SERVICE_TIMES:
            return None
        taken = self._taken_tables(date_, time)
        candidates = sorted(
            ((label, seats) for label, seats in TABLES.items() if seats >= party_size),
            key=lambda x: x[1],
        )
        for label, _ in candidates:
            if label not in taken:
                return label
        return None

    def is_available(self, date_: str, time: str, party_size: int) -> bool:
        return self.find_table(date_, time, party_size) is not None

    def alternatives(
        self, date_: str, time: str, party_size: int, limit: int = 3
    ) -> list[str]:
        """Suggest nearby open times on the same date."""
        if time not in SERVICE_TIMES:
            base_idx = len(SERVICE_TIMES) // 2
        else:
            base_idx = SERVICE_TIMES.index(time)

        ordered: list[str] = []
        for offset in range(1, len(SERVICE_TIMES)):
            for idx in (base_idx - offset, base_idx + offset):
                if 0 <= idx < len(SERVICE_TIMES):
                    t = SERVICE_TIMES[idx]
                    if t not in ordered:
                        ordered.append(t)

        found: list[str] = []
        for t in ordered:
            if self.find_table(date_, t, party_size):
                found.append(t)
            if len(found) >= limit:
                break
        return found

    def book(
        self,
        date_: str,
        time: str,
        party_size: int,
        guest_name: Optional[str] = None,
    ) -> Optional[BookingRecord]:
        table = self.find_table(date_, time, party_size)
        if not table:
            return None
        rec = BookingRecord(
            id=f"HLB-{uuid.uuid4().hex[:8].upper()}",
            date=date_,
            time=time,
            party_size=party_size,
            table_label=table,
            guest_name=guest_name,
            status="active",
        )
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO bookings
                    (id, restaurant, date, time, party_size, table_label, guest_name, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.id,
                    rec.restaurant,
                    rec.date,
                    rec.time,
                    rec.party_size,
                    rec.table_label,
                    rec.guest_name,
                    rec.status,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT created_at FROM bookings WHERE id = ?", (rec.id,)
            ).fetchone()
            if row:
                rec.created_at = row["created_at"]
        finally:
            conn.close()
        return rec

    def list_bookings(
        self,
        date_: Optional[str] = None,
        *,
        booking_id: Optional[str] = None,
        include_cancelled: bool = True,
    ) -> list[BookingRecord]:
        conn = self._conn()
        try:
            clauses: list[str] = []
            params: list = []
            if booking_id:
                clauses.append("id LIKE ?")
                params.append(f"%{booking_id.strip()}%")
            if date_:
                clauses.append("date = ?")
                params.append(date_)
            if not include_cancelled:
                clauses.append("status = 'active'")
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = conn.execute(
                f"""
                SELECT id, restaurant, date, time, party_size, table_label,
                       guest_name, status, created_at
                FROM bookings{where}
                ORDER BY date, time, id
                """,
                params,
            ).fetchall()
            return [_row_to_record(r) for r in rows]
        finally:
            conn.close()

    def get_booking(self, booking_id: str) -> Optional[BookingRecord]:
        conn = self._conn()
        try:
            r = conn.execute(
                """
                SELECT id, restaurant, date, time, party_size, table_label,
                       guest_name, status, created_at
                FROM bookings WHERE id = ?
                """,
                (booking_id,),
            ).fetchone()
            if not r:
                return None
            return _row_to_record(r)
        finally:
            conn.close()

    def cancel_booking(self, booking_id: str) -> bool:
        """Soft-cancel: mark status cancelled (frees the table)."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """
                UPDATE bookings SET status = 'cancelled'
                WHERE id = ? AND status = 'active'
                """,
                (booking_id,),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def restore_booking(self, booking_id: str) -> bool:
        """Restore a cancelled booking if the table is still free."""
        rec = self.get_booking(booking_id)
        if not rec or rec.status != "cancelled":
            return False
        # Table must be free for that slot
        taken = self._taken_tables(rec.date, rec.time)
        if rec.table_label in taken:
            return False
        conn = self._conn()
        try:
            cur = conn.execute(
                """
                UPDATE bookings SET status = 'active'
                WHERE id = ? AND status = 'cancelled'
                """,
                (booking_id,),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def open_slots(self, date_: str, party_size: int = 2) -> list[str]:
        """Service times that still have a table for party_size on date."""
        return [t for t in SERVICE_TIMES if self.find_table(date_, t, party_size)]

    def stats(self, today: Optional[str] = None) -> dict:
        today = today or date.today().isoformat()
        conn = self._conn()
        try:
            total_active = conn.execute(
                "SELECT COUNT(*) AS c FROM bookings WHERE status = 'active'"
            ).fetchone()["c"]
            total_cancelled = conn.execute(
                "SELECT COUNT(*) AS c FROM bookings WHERE status = 'cancelled'"
            ).fetchone()["c"]
            today_row = conn.execute(
                """
                SELECT COUNT(*) AS c, COALESCE(SUM(party_size), 0) AS seats
                FROM bookings WHERE date = ? AND status = 'active'
                """,
                (today,),
            ).fetchone()
            return {
                "total_active": int(total_active),
                "total_cancelled": int(total_cancelled),
                "today_count": int(today_row["c"]),
                "today_seats": int(today_row["seats"]),
                "today": today,
            }
        finally:
            conn.close()

    def export_csv(
        self,
        date_: Optional[str] = None,
        *,
        include_cancelled: bool = True,
    ) -> str:
        rows = self.list_bookings(date_=date_, include_cancelled=include_cancelled)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id",
                "restaurant",
                "date",
                "time",
                "party_size",
                "table_label",
                "guest_name",
                "status",
                "created_at",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r.id,
                    r.restaurant,
                    r.date,
                    r.time,
                    r.party_size,
                    r.table_label,
                    r.guest_name or "",
                    r.status,
                    r.created_at or "",
                ]
            )
        return buf.getvalue()

    def seed_demo(self, today: Optional[str] = None) -> list[BookingRecord]:
        """Insert a few fake past/today bookings for admin demos (skips conflicts)."""
        today_d = date.fromisoformat(today) if today else date.today()
        yesterday = (today_d - timedelta(days=1)).isoformat()
        today_s = today_d.isoformat()
        plan = [
            (yesterday, "18:00", 2, "Maya"),
            (yesterday, "19:30", 4, "Omar"),
            (today_s, "17:30", 2, "Priya"),
            (today_s, "19:00", 6, "Jordan"),
            (today_s, "20:00", 3, "Sam"),
        ]
        created: list[BookingRecord] = []
        for d, t, party, name in plan:
            rec = self.book(d, t, party, guest_name=name)
            if rec:
                created.append(rec)
        return created

    def count_bookings(self, *, active_only: bool = False) -> int:
        conn = self._conn()
        try:
            if active_only:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM bookings WHERE status = 'active'"
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) AS c FROM bookings").fetchone()
            return int(row["c"])
        finally:
            conn.close()

    def reset(self) -> None:
        """Clear all bookings (used by tests)."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM bookings")
            conn.commit()
        finally:
            conn.close()


# Shared store for the running process (path from env / default)
store = AvailabilityStore()


def rebind_store(path) -> AvailabilityStore:
    """Point the module-level store at a different DB file (tests)."""
    global store
    store = AvailabilityStore(path)
    return store


def active_db_path() -> str:
    return str(store._path or db_path())
