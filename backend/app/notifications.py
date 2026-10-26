"""Fake confirmation notifications — log only, never send email/SMS (free)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.db import db_path


def notifications_path() -> Path:
    raw = os.environ.get("NOTIFICATIONS_LOG", "").strip()
    if raw:
        return Path(raw)
    return db_path().parent / "notifications.log"


def log_confirmation(
    *,
    booking_id: str,
    date: str,
    time: str,
    party_size: int,
    guest_name: Optional[str] = None,
    restaurant: str = "Harbor Lights Bistro",
) -> str:
    """Append a fake email + SMS line. Returns the line written."""
    path = notifications_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    guest = guest_name or "guest"
    line = (
        f"{ts} | FAKE_EMAIL+SMS | to={guest} | "
        f"booking={booking_id} | {restaurant} | {date} {time} | party={party_size}\n"
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
    return line.strip()
