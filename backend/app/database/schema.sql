-- Fictional restaurant inventory. A reservation uses exactly one table.
CREATE TABLE IF NOT EXISTS restaurant_tables (
    table_id INTEGER PRIMARY KEY,
    capacity INTEGER NOT NULL CHECK (typeof(capacity) = 'integer' AND capacity BETWEEN 1 AND 20)
);

CREATE TABLE IF NOT EXISTS reservations (
    reservation_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(reservation_id)) > 0),
    request_id TEXT NOT NULL UNIQUE CHECK (length(trim(request_id)) BETWEEN 1 AND 128),
    reservation_date TEXT NOT NULL CHECK (
        reservation_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        AND date(reservation_date, '+0 days') IS NOT NULL
        AND date(reservation_date, '+0 days') = reservation_date
    ),
    reservation_time TEXT NOT NULL CHECK (
        reservation_time GLOB '[0-9][0-9]:[0-9][0-9]'
        AND CAST(substr(reservation_time, 4, 2) AS INTEGER) BETWEEN 0 AND 59
        AND reservation_time BETWEEN '11:00' AND '21:30'
    ),
    party_size INTEGER NOT NULL CHECK (typeof(party_size) = 'integer' AND party_size BETWEEN 1 AND 20),
    table_id INTEGER NOT NULL REFERENCES restaurant_tables(table_id),
    start_minute INTEGER NOT NULL CHECK (
        typeof(start_minute) = 'integer'
        AND start_minute = CAST(substr(reservation_time, 1, 2) AS INTEGER) * 60
                         + CAST(substr(reservation_time, 4, 2) AS INTEGER)
    ),
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS reservation_availability
ON reservations(reservation_date, table_id, start_minute) WHERE status = 'confirmed';

CREATE UNIQUE INDEX IF NOT EXISTS reservation_same_start
ON reservations(table_id, reservation_date, start_minute) WHERE status = 'confirmed';

-- These guards also protect writes made outside ReservationStore.
CREATE TRIGGER IF NOT EXISTS reservation_insert_capacity
BEFORE INSERT ON reservations
WHEN NOT EXISTS (
    SELECT 1 FROM restaurant_tables
    WHERE table_id = NEW.table_id AND capacity >= NEW.party_size
)
BEGIN
    SELECT RAISE(ABORT, 'table capacity exceeded or table does not exist');
END;

CREATE TRIGGER IF NOT EXISTS reservation_update_capacity
BEFORE UPDATE ON reservations
WHEN NOT EXISTS (
    SELECT 1 FROM restaurant_tables
    WHERE table_id = NEW.table_id AND capacity >= NEW.party_size
)
BEGIN
    SELECT RAISE(ABORT, 'table capacity exceeded or table does not exist');
END;

-- Intervals are [start, start + 90 minutes); adjacent reservations may touch.
CREATE TRIGGER IF NOT EXISTS reservation_insert_overlap
BEFORE INSERT ON reservations
WHEN NEW.status = 'confirmed' AND EXISTS (
    SELECT 1 FROM reservations
    WHERE table_id = NEW.table_id AND reservation_date = NEW.reservation_date
      AND status = 'confirmed'
      AND start_minute < NEW.start_minute + 90
      AND start_minute + 90 > NEW.start_minute
)
BEGIN
    SELECT RAISE(ABORT, 'reservation conflict');
END;

CREATE TRIGGER IF NOT EXISTS reservation_update_overlap
BEFORE UPDATE ON reservations
WHEN NEW.status = 'confirmed' AND EXISTS (
    SELECT 1 FROM reservations
    WHERE table_id = NEW.table_id AND reservation_date = NEW.reservation_date
      AND reservation_id != OLD.reservation_id AND status = 'confirmed'
      AND start_minute < NEW.start_minute + 90
      AND start_minute + 90 > NEW.start_minute
)
BEGIN
    SELECT RAISE(ABORT, 'reservation conflict');
END;

CREATE TRIGGER IF NOT EXISTS table_capacity_update
BEFORE UPDATE OF capacity ON restaurant_tables
WHEN EXISTS (
    SELECT 1 FROM reservations
    WHERE table_id = OLD.table_id AND party_size > NEW.capacity
)
BEGIN
    SELECT RAISE(ABORT, 'existing reservation exceeds table capacity');
END;
