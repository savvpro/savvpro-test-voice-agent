"""SQLite persistence for Harbor Lights bookings (stdlib only, free)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

# Default: backend/data/bookings.db  — override with BOOKINGS_DB env
_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "bookings.db"


def db_path() -> Path:
    raw = os.environ.get("BOOKINGS_DB", "").strip()
    if raw:
        return Path(raw)
    return _DEFAULT


def connect(path: Optional[Path | str] = None) -> sqlite3.Connection:
    p = Path(path) if path is not None else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Optional[Path | str] = None) -> None:
    """Create tables if they do not exist; soft-migrate status column."""
    conn = connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id TEXT PRIMARY KEY,
                restaurant TEXT NOT NULL DEFAULT 'Harbor Lights Bistro',
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                party_size INTEGER NOT NULL,
                table_label TEXT NOT NULL,
                guest_name TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        # Soft migrate older DBs that lack status
        cols = {
            r["name"]
            for r in conn.execute("PRAGMA table_info(bookings)").fetchall()
        }
        if "status" not in cols:
            conn.execute(
                "ALTER TABLE bookings ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bookings_date_time ON bookings(date, time)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status)"
        )
        conn.commit()
    finally:
        conn.close()


def ping_db(path: Optional[Path | str] = None) -> bool:
    """Return True if SQLite answers a trivial query."""
    try:
        conn = connect(path)
        try:
            conn.execute("SELECT 1").fetchone()
            return True
        finally:
            conn.close()
    except Exception:
        return False
