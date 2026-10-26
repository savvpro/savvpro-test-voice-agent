"""SQLite persistence, validation, idempotency, and transaction regressions.

Every database lives under pytest's tmp_path; no test uses the development file.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Barrier

import pytest

from app.database import (
    IdempotencyConflictError,
    InvalidReservationError,
    ReservationStore,
    UnavailableError,
)
from app.database.reservations import FAKE_TABLES


TODAY = date(2026, 10, 26)
DAY = "2026-10-27"


@pytest.fixture
def store(tmp_path):
    result = ReservationStore(tmp_path / "restaurant.sqlite3", today=lambda: TODAY)
    result.initialize_database()
    return result


def book(store, key="fake-submission", day=DAY, time="19:00", guests=4):
    return store.create_reservation(day, time, guests, request_id=key)


@contextmanager
def raw_connection(store):
    connection = sqlite3.connect(store.database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def raw_insert(connection, *, key="raw", day=DAY, time="19:00", guests=4,
               table=3, start=1140, status="confirmed"):
    connection.execute(
        """INSERT INTO reservations (
               reservation_id, request_id, reservation_date, reservation_time,
               party_size, table_id, start_minute, status
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (key, key, day, time, guests, table, start, status),
    )


def test_initialization_is_explicit_and_seeds_only_fake_tables(tmp_path):
    path = tmp_path / "nested" / "restaurant.sqlite3"
    store = ReservationStore(path, today=lambda: TODAY)
    assert not path.exists()
    store.initialize_database()
    assert path.is_file()
    assert store.list_reservations() == []
    assert [(t.table_id, t.capacity) for t in store.check_availability(DAY, "19:00", 1)] == list(FAKE_TABLES)
    with raw_connection(store) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(reservations)")}
    assert not columns.intersection({"name", "email", "phone", "customer_id"})


def test_successful_creation_has_required_fields_and_smallest_table(store):
    result = book(store)
    assert result.reservation_id
    assert result.reservation_date == DAY
    assert result.reservation_time == "19:00"
    assert result.party_size == 4
    assert result.status == "confirmed"
    assert result.request_id == "fake-submission"
    assert result.table_id == 3
    assert datetime.fromisoformat(result.created_at.replace("Z", "+00:00")).utcoffset() == timedelta(0)
    assert store.get_reservation(result.reservation_id) == result
    assert store.get_reservation("missing") is None


def test_persistence_after_reopening_and_reinitialization(store):
    original = book(store)
    reopened = ReservationStore(store.database_path, today=lambda: TODAY)
    reopened.initialize_database()
    assert reopened.get_reservation(original.reservation_id) == original
    assert reopened.list_reservations() == [original]
    assert len(reopened.check_availability(DAY, "19:00", 1)) == 5


def test_initialization_cli_uses_explicit_temporary_path(tmp_path):
    path = tmp_path / "cli.sqlite3"
    result = subprocess.run(
        [sys.executable, "-m", "app.database", "--path", str(path)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True,
    )
    assert "Initialized reservation database" in result.stdout
    assert ReservationStore(path).list_reservations() == []


def test_database_reopens_in_another_process(store):
    original = book(store)
    result = subprocess.run(
        [sys.executable, "-c",
         "from app.database import ReservationStore; import sys; "
         "r=ReservationStore(sys.argv[1]).get_reservation(sys.argv[2]); "
         "print(r.reservation_id, r.party_size, r.status)",
         str(store.database_path), original.reservation_id],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == f"{original.reservation_id} 4 confirmed"


def test_availability_is_read_only_and_does_not_hold_a_table(store):
    first = store.check_availability(DAY, "19:00", 20)
    assert [(t.table_id, t.capacity) for t in first] == [(6, 20)]
    assert store.check_availability(DAY, "19:00", 20) == first
    assert store.list_reservations() == []
    assert book(store, guests=20).table_id == 6
    assert store.check_availability(DAY, "19:00", 20) == []


def test_same_slot_different_keys_assign_distinct_tables_until_full(store):
    records = [book(store, key=f"party-{i}", guests=1) for i in range(6)]
    assert [r.table_id for r in records] == [1, 2, 3, 4, 5, 6]
    assert len({r.reservation_id for r in records}) == 6
    assert store.check_availability(DAY, "19:00", 1) == []
    with pytest.raises(UnavailableError):
        book(store, key="full", guests=1)
    assert len(store.list_reservations()) == 6


def test_free_smaller_tables_cannot_accommodate_large_party(store):
    book(store, guests=20)
    assert store.check_availability(DAY, "19:00", 20) == []
    assert store.check_availability(DAY, "19:00", 2)
    with pytest.raises(UnavailableError):
        book(store, key="another-large-party", guests=9)


@pytest.mark.parametrize("time", ["17:31", "18:00", "19:00", "19:30", "20:29"])
def test_overlapping_intervals_block_same_table(store, time):
    book(store, guests=20)
    assert store.check_availability(DAY, time, 20) == []
    with pytest.raises(UnavailableError):
        book(store, key="overlap", guests=20, time=time)
    assert len(store.list_reservations()) == 1


@pytest.mark.parametrize("time", ["17:30", "20:30"])
def test_adjacent_intervals_can_reuse_table(store, time):
    original = book(store, guests=20)
    assert book(store, key="adjacent", time=time, guests=20).table_id == original.table_id


def test_other_dates_do_not_conflict(store):
    first = book(store, guests=20)
    assert book(store, key="next-day", day="2026-10-28", guests=20).table_id == first.table_id


def test_duplicate_retry_returns_same_record_even_when_capacity_full(store):
    original = book(store, key="retry", guests=20)
    assert book(store, key="retry", guests=20) == original
    reopened = ReservationStore(store.database_path, today=lambda: TODAY)
    assert book(reopened, key="retry", guests=20) == original
    assert store.list_reservations() == [original]


def test_retry_returns_original_even_after_booking_date_passes(store):
    original = book(store, key="retry", guests=20)
    later = ReservationStore(store.database_path, today=lambda: date(2026, 11, 1))
    assert book(later, key="retry", guests=20) == original
    with pytest.raises(InvalidReservationError):
        book(later, key="new", guests=20)


@pytest.mark.parametrize("change", [dict(time="20:30"), dict(guests=6), dict(day="2026-10-28")])
def test_same_submission_key_different_details_rejected(store, change):
    original = book(store, key="same")
    with pytest.raises(IdempotencyConflictError):
        book(store, key="same", **change)
    assert store.list_reservations() == [original]


def test_submission_key_normalization_and_bound_sql_parameters(store):
    original = book(store, key="  fake-key  ")
    assert book(store, key="fake-key") == original
    injection = "fake'); DROP TABLE reservations; --"
    assert book(store, key=injection).request_id == injection
    assert len(store.list_reservations()) == 2


@pytest.mark.parametrize("key", [None, "", "  ", "x" * 129, 42])
def test_invalid_submission_keys_are_not_saved(store, key):
    with pytest.raises(InvalidReservationError):
        book(store, key=key)
    assert store.list_reservations() == []


@pytest.mark.parametrize(
    "day,time,guests",
    [
        ("2026-02-30", "19:00", 4), ("2026-04-31", "19:00", 4),
        ("2026-2-03", "19:00", 4), ("tomorrow", "19:00", 4),
        (None, "19:00", 4), ("2026-10-25", "19:00", 4),
        ("2027-01-25", "19:00", 4), (DAY, "7:99pm", 4),
        (DAY, "25:00", 4), (DAY, "13:75", 4), (DAY, "19:30:99", 4),
        (DAY, "7:00", 4), (DAY, "10:59", 4), (DAY, "21:31", 4),
        (DAY, None, 4), (DAY, "19:00", -2), (DAY, "19:00", 0),
        (DAY, "19:00", 21), (DAY, "19:00", 4.0), (DAY, "19:00", True),
        (DAY, "19:00", "4"), (DAY, "19:00", None),
    ],
)
def test_invalid_details_rejected_by_create_and_availability(store, day, time, guests):
    with pytest.raises(InvalidReservationError):
        store.create_reservation(day, time, guests, request_id="invalid")
    with pytest.raises(InvalidReservationError):
        store.check_availability(day, time, guests)
    assert store.list_reservations() == []


@pytest.mark.parametrize("day,time,guests", [
    ("2026-10-26", "11:00", 1), ("2027-01-24", "21:30", 20),
])
def test_booking_policy_boundaries_are_inclusive(store, day, time, guests):
    assert book(store, day=day, time=time, guests=guests).status == "confirmed"


def test_failed_creation_does_not_consume_submission_key(store):
    book(store, key="occupied", guests=20)
    with pytest.raises(UnavailableError):
        book(store, key="try-again", guests=20)
    assert book(store, key="try-again", guests=20, time="20:30").request_id == "try-again"


def test_transaction_rolls_back_if_insert_is_aborted(store):
    with raw_connection(store) as connection:
        connection.execute("""CREATE TRIGGER simulate_failure AFTER INSERT ON reservations
                              BEGIN SELECT RAISE(ABORT, 'simulated failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="simulated failure"):
        book(store)
    assert store.list_reservations() == []
    with raw_connection(store) as connection:
        connection.execute("DROP TRIGGER simulate_failure")
    assert book(store).status == "confirmed"


def test_concurrent_different_submissions_cannot_double_book(store):
    barrier = Barrier(2)

    def attempt(key):
        independent_store = ReservationStore(store.database_path, today=lambda: TODAY)
        barrier.wait(timeout=10)
        try:
            return book(independent_store, key=key, guests=20)
        except UnavailableError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ["writer-1", "writer-2"]))
    assert sum(result is not None for result in results) == 1
    assert len(store.list_reservations()) == 1


def test_concurrent_identical_submissions_return_one_reservation(store):
    barrier = Barrier(2)

    def attempt(_):
        independent_store = ReservationStore(store.database_path, today=lambda: TODAY)
        barrier.wait(timeout=10)
        return book(independent_store, key="same-request", guests=20)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))
    assert results[0] == results[1]
    assert store.list_reservations() == [results[0]]


@pytest.mark.parametrize("change", [
    dict(day="2026-02-30"), dict(time="19:99"), dict(guests=0),
    dict(guests=-2), dict(guests=21), dict(guests=4.5), dict(status="unknown"),
    dict(table=1, guests=4), dict(table=999), dict(start=1139),
])
def test_database_constraints_reject_invalid_direct_inserts(store, change):
    with raw_connection(store) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            raw_insert(connection, **change)
    assert store.list_reservations() == []


def test_database_trigger_rejects_overlapping_direct_insert(store):
    book(store, guests=20)
    with raw_connection(store) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="reservation conflict"):
            raw_insert(connection, table=6, guests=20, time="19:30", start=1170)
    assert len(store.list_reservations()) == 1


def test_database_unique_constraint_rejects_duplicate_submission(store):
    book(store, key="same", guests=20)
    with raw_connection(store) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="request_id"):
            raw_insert(connection, key="different-id", time="20:30", start=1230)
            connection.execute("UPDATE reservations SET request_id = 'same' WHERE reservation_id = 'different-id'")
        connection.rollback()
    assert len(store.list_reservations()) == 1


def test_update_trigger_blocks_overlapping_reschedule(store):
    first = book(store, key="first", guests=20)
    second = book(store, key="second", guests=20, time="20:30")
    with raw_connection(store) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="reservation conflict"):
            connection.execute(
                "UPDATE reservations SET reservation_time = '20:00', start_minute = 1200 WHERE reservation_id = ?",
                (second.reservation_id,),
            )
    assert store.get_reservation(first.reservation_id) == first
    assert store.get_reservation(second.reservation_id) == second


def test_capacity_updates_cannot_invalidate_existing_reservations(store):
    original = book(store, guests=4)
    with raw_connection(store) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="capacity"):
            connection.execute("UPDATE reservations SET party_size = 5 WHERE reservation_id = ?", (original.reservation_id,))
        with pytest.raises(sqlite3.IntegrityError, match="capacity"):
            connection.execute("UPDATE restaurant_tables SET capacity = 2 WHERE table_id = ?", (original.table_id,))
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute("DELETE FROM restaurant_tables WHERE table_id = ?", (original.table_id,))
    assert store.get_reservation(original.reservation_id) == original


def test_cancelled_rows_do_not_block_capacity_and_cannot_conflictingly_reactivate(store):
    original = book(store, key="cancelled-row", guests=20)
    with raw_connection(store) as connection:
        connection.execute("UPDATE reservations SET status = 'cancelled' WHERE reservation_id = ?", (original.reservation_id,))
    assert store.check_availability(DAY, "19:00", 20)
    book(store, key="replacement", guests=20)
    with raw_connection(store) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="reservation conflict"):
            connection.execute("UPDATE reservations SET status = 'confirmed' WHERE reservation_id = ?", (original.reservation_id,))
    assert store.get_reservation(original.reservation_id).status == "cancelled"


def test_independent_database_files_do_not_share_inventory(store, tmp_path):
    other = ReservationStore(tmp_path / "other.sqlite3", today=lambda: TODAY)
    other.initialize_database()
    book(store, guests=20)
    assert book(other, key="independent", guests=20).status == "confirmed"


def test_memory_database_rejected_because_connections_are_short_lived():
    with pytest.raises(ValueError, match="file path"):
        ReservationStore(":memory:")
