# Phase 3: SQLite reservation storage

The `app.database` package uses Python's standard-library `sqlite3`. It does not
import the decision-making brain or FastAPI, and those components do not import
it. Importing the package creates no files. Phase 3 provides the persistence
API; the Phase 4 conversation service and HTTP endpoints are documented in
[API.md](API.md).

## Setup and use

From `backend`, initialize the development database explicitly:

```powershell
python -m app.database
```

The default is `backend/data/reservations.sqlite3`. An alternative file can be
selected with `python -m app.database --path path/to/restaurant.sqlite3`.
Initialization creates parent directories, schema, and fictional table inventory
in one transaction. Repeating it preserves existing reservations and inventory.
SQLite database files and their journal files are ignored by Git.

The repository provides these methods:

```python
from datetime import date, timedelta
from app.database import DEFAULT_DATABASE_PATH, ReservationStore

store = ReservationStore(DEFAULT_DATABASE_PATH)
store.initialize_database()
day = (date.today() + timedelta(days=1)).isoformat()
available = store.check_availability(day, "19:00", 4)
reservation = store.create_reservation(
    day, "19:00", 4, request_id="fake-conversation-001-confirmation-001",
)
same_reservation = store.create_reservation(
    day, "19:00", 4, request_id="fake-conversation-001-confirmation-001",
)
assert reservation == same_reservation
saved = store.get_reservation(reservation.reservation_id)
all_reservations = store.list_reservations()
```

`check_availability` returns fitting free tables, smallest first. It does not
hold a table; another booking can use it before creation. Creation always checks
again inside its write transaction. `get_reservation` returns `None` for an
unknown ID. Methods return immutable dataclasses rather than SQLite connections.
Every operation closes its connection. No ORM or additional dependency is needed.

## Fictional restaurant policy

All inventory is fake and no customer names, emails, phone numbers, or other
personal data are stored.

| Table IDs | Capacity per table | Number of tables |
| --- | --- | --- |
| 1, 2 | 2 | 2 |
| 3, 4 | 4 | 2 |
| 5 | 8 | 1 |
| 6 | 20 | 1 |

The restaurant has 40 seats across six tables. Each booking uses exactly one
table; tables cannot be combined or shared between simultaneous parties.
Allocation chooses the smallest fitting free table, breaking ties by table ID.
Unused seats on an occupied table are unavailable to other bookings.

* Party size must be a Python integer from 1 through 20; booleans, floats,
  strings, zero, and negative values are rejected.
* Dates must be real calendar dates in exact `YYYY-MM-DD` form, from today
  through today + 90 days, inclusive.
* Starts must use exact `HH:MM` 24-hour form, between 11:00 and 21:30 inclusive.
  Any minute in this interval is accepted; there is no slot grid.
* Occupancy lasts exactly 90 minutes. Intervals are half-open: a 19:00 booking
  occupies its table until 20:30; another may start at 20:30, but not at 20:29.
* Last seating limits the start, not the end of occupancy; a 21:30 start blocks
  its table until 23:00. No booking crosses midnight under this policy.
* Stored dates and times are restaurant-local wall time. The restaurant's
  configured local date is supplied by `today` (default `date.today`, so the
  development host must use the restaurant's timezone). Tests inject a clock.
  Creation timestamps are UTC, with a trailing `Z`.
* As in Phase 2, same-day starts are checked against business hours, not the
  current minute. Holidays, closures, and variable dining durations are not modeled.

## Structure

`restaurant_tables` stores `table_id` and `capacity`.

`reservations` stores:

| Column | Purpose |
| --- | --- |
| `reservation_id` | Generated UUID hex string, primary key |
| `reservation_date` | Normalized date |
| `reservation_time` | Normalized seating start |
| `party_size` | Number of guests |
| `status` | `confirmed` or `cancelled`; creation always uses `confirmed` |
| `created_at` | SQLite-generated UTC creation timestamp |
| `table_id` | Foreign key to the assigned fictional table |
| `request_id` | Unique caller-supplied idempotency key |
| `start_minute` | Minutes since midnight, constrained to match the stored time |

Indexes support availability queries and reject duplicate active start times
for a table. CHECK constraints enforce canonical calendar dates, seating times,
party bounds, minute consistency, and supported statuses. Foreign keys are
enabled on every repository connection. Insert/update triggers enforce table
capacity and reject overlapping confirmed reservations; capacity changes that
would invalidate existing reservations are rejected as well.

## Duplicate submissions and conflicting bookings

The caller must retain the **same `request_id` for retries of one booking** and
use a new key for a genuinely new reservation. Keys contain 1 to 128 characters;
surrounding whitespace is stripped. No customer identity is needed.

* The same key and identical date/time/guest count return the original record,
  including ID, assigned table, status, and timestamp, without another insert.
  This also works after reopening the database and after the original date passes.
* Reusing a key with different details raises `IdempotencyConflictError`.
* Different keys with identical details are separate legitimate parties and can
  book separate tables when capacity permits. Without customer information the
  system cannot infer that different keys belong to the same human submission.
* `BEGIN IMMEDIATE` takes SQLite's write lock **before** looking up keys or
  checking availability. The key lookup, table assignment, and insert commit
  together; exceptions roll back the transaction. Concurrent writers therefore
  cannot both claim the same available table.
* A unique key constraint and database overlap/capacity triggers provide another
  layer of protection, including for direct SQL inserts, rescheduling, and
  reactivation of cancelled rows. Cancelled rows do not occupy capacity.
* An unavailable request raises `UnavailableError` without consuming its key.
  A later attempt may reuse that key. Invalid input raises `InvalidReservationError`.

SQLite waits up to 10 seconds for locks. A longer lock or filesystem failure
surfaces as a `sqlite3` exception; there is no background retry queue. The booking
window is validated in Python because it depends on the injected current date;
the database independently checks static structural and capacity constraints.

## Verification and phase boundaries

From `backend`:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_database.py
python -m pytest -q -p no:cacheprovider
python -m tests.check_phase2_conversations
```

Database tests use pytest's `tmp_path`, never the development file. Tests cover
creation, reopening in another object and process, initialization/CLI behavior,
validation, capacity exhaustion, interval boundaries, different dates, repeated
submissions, rollback, direct-SQL constraints/triggers, and concurrent writers.
On systems restricting pytest's default temporary directory, use a fresh,
disposable `--basetemp` directory (pytest removes any existing contents there).

The storage layer adds no React UI, speech integration, or imports of storage
from the brain. The Phase 4 service coordinates storage from outside the brain.
Public cancellation/rescheduling operations, schema
migrations, backups, and authentication are not implemented. The status column
and update triggers support later work without introducing those workflows now.
