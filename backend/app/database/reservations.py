"""Persistent storage for fictional restaurant reservations using only sqlite3.

No brain or FastAPI imports. Initialization is explicit; importing this module
does not create a database. See backend/DATABASE.md for the availability policy.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Iterator


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "reservations.sqlite3"
FAKE_TABLES = ((1, 2), (2, 2), (3, 4), (4, 4), (5, 8), (6, 20))
BOOKING_DURATION_MINUTES = 90
MAX_ADVANCE_DAYS = 90


class InvalidReservationError(ValueError):
    """Details are malformed or outside the restaurant's booking policy."""


class UnavailableError(Exception):
    """No suitably sized table is free for the complete reservation interval."""


class IdempotencyConflictError(Exception):
    """A submission key was previously used with different reservation details."""


@dataclass(frozen=True)
class Table:
    table_id: int
    capacity: int


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    reservation_date: str
    reservation_time: str
    party_size: int
    table_id: int
    status: str
    created_at: str
    request_id: str


class ReservationStore:
    """One file-backed database; each operation owns and closes its connection.

    The caller must keep the same request_id when retrying a submission. A new
    logical booking needs a new key, even when its date/time/party size match.
    """

    def __init__(
        self,
        database_path: str | Path,
        *,
        today: Callable[[], date] = date.today,
    ) -> None:
        if str(database_path) == ":memory:":
            raise ValueError("Use a file path; operations use independent connections.")
        self.database_path = Path(database_path)
        self._today = today

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connection() as connection:
            # Serialize writers BEFORE looking at keys or available tables.
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def initialize_database(self) -> None:
        """Create schema and seed fictional tables, safely on repeated calls."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with self._connection() as connection:
            # executescript commits an existing transaction, so BEGIN belongs
            # inside the script and the seed inserts share that transaction.
            try:
                connection.executescript("BEGIN IMMEDIATE;\n" + schema)
                connection.executemany(
                    "INSERT OR IGNORE INTO restaurant_tables(table_id, capacity) VALUES (?, ?)",
                    FAKE_TABLES,
                )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def check_availability(
        self, reservation_date: str, reservation_time: str, party_size: int,
    ) -> list[Table]:
        """Return fitting free tables, smallest first; this does not hold a table."""
        start_minute = self._validate_details(reservation_date, reservation_time, party_size)
        self._validate_booking_window(reservation_date)
        with self._connection() as connection:
            return self._available_tables(connection, reservation_date, start_minute, party_size)

    def create_reservation(
        self,
        reservation_date: str,
        reservation_time: str,
        party_size: int,
        *,
        request_id: str,
    ) -> Reservation:
        """Atomically assign a table, or return the result of an identical retry.

        Reusing a key with different details raises IdempotencyConflictError.
        Insufficient capacity raises UnavailableError without consuming the key.
        """
        start_minute = self._validate_details(reservation_date, reservation_time, party_size)
        if not isinstance(request_id, str) or not 1 <= len(request_id.strip()) <= 128:
            raise InvalidReservationError("request_id must contain 1 to 128 characters.")
        request_id = request_id.strip()

        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM reservations WHERE request_id = ?", (request_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["reservation_date"], existing["reservation_time"], existing["party_size"]
                ) != (reservation_date, reservation_time, party_size):
                    raise IdempotencyConflictError("request_id already belongs to different details.")
                # Replays still return the original record after its date passes.
                return self._reservation(existing)

            self._validate_booking_window(reservation_date)
            tables = self._available_tables(connection, reservation_date, start_minute, party_size)
            if not tables:
                raise UnavailableError("No suitable table is available for this 90-minute reservation.")

            reservation_id = uuid.uuid4().hex
            connection.execute(
                """INSERT INTO reservations (
                    reservation_id, request_id, reservation_date, reservation_time,
                    party_size, table_id, start_minute
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (reservation_id, request_id, reservation_date, reservation_time,
                 party_size, tables[0].table_id, start_minute),
            )
            row = connection.execute(
                "SELECT * FROM reservations WHERE reservation_id = ?", (reservation_id,),
            ).fetchone()
            return self._reservation(row)

    def get_reservation(self, reservation_id: str) -> Reservation | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM reservations WHERE reservation_id = ?", (reservation_id,),
            ).fetchone()
            return self._reservation(row) if row is not None else None

    def list_reservations(self) -> list[Reservation]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM reservations ORDER BY created_at, reservation_id",
            ).fetchall()
            return [self._reservation(row) for row in rows]

    @staticmethod
    def _reservation(row: sqlite3.Row) -> Reservation:
        return Reservation(**{name: row[name] for name in Reservation.__dataclass_fields__})

    @staticmethod
    def _available_tables(
        connection: sqlite3.Connection, reservation_date: str, start_minute: int, party_size: int,
    ) -> list[Table]:
        rows = connection.execute(
            """SELECT t.table_id, t.capacity FROM restaurant_tables AS t
               WHERE t.capacity >= ? AND NOT EXISTS (
                   SELECT 1 FROM reservations AS r
                   WHERE r.table_id = t.table_id AND r.reservation_date = ?
                     AND r.status = 'confirmed'
                     AND r.start_minute < ? AND r.start_minute + 90 > ?
               ) ORDER BY t.capacity, t.table_id""",
            (party_size, reservation_date, start_minute + BOOKING_DURATION_MINUTES, start_minute),
        ).fetchall()
        return [Table(**dict(row)) for row in rows]

    @staticmethod
    def _validate_details(reservation_date: str, reservation_time: str, party_size: int) -> int:
        if not isinstance(reservation_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", reservation_date):
            raise InvalidReservationError("Date must use YYYY-MM-DD format.")
        try:
            date.fromisoformat(reservation_date)
        except ValueError as error:
            raise InvalidReservationError("Date must be a valid calendar date.") from error
        if not isinstance(reservation_time, str) or not re.fullmatch(r"[0-9]{2}:[0-9]{2}", reservation_time):
            raise InvalidReservationError("Time must use HH:MM 24-hour format.")
        hour, minute = map(int, reservation_time.split(":"))
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise InvalidReservationError("Time must be a valid 24-hour time.")
        start_minute = hour * 60 + minute
        if not 11 * 60 <= start_minute <= 21 * 60 + 30:
            raise InvalidReservationError("Seating times must be between 11:00 and 21:30 inclusive.")
        if type(party_size) is not int or not 1 <= party_size <= 20:
            raise InvalidReservationError("Number of guests must be an integer from 1 to 20.")
        return start_minute

    def _validate_booking_window(self, reservation_date: str) -> None:
        requested = date.fromisoformat(reservation_date)
        today = self._today()
        if not today <= requested <= today + timedelta(days=MAX_ADVANCE_DAYS):
            raise InvalidReservationError("Date must be today or within the next 90 days.")
