#!/usr/bin/env python3
"""Seed a few fake bookings for local admin demos. Free / offline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine.availability import AvailabilityStore  # noqa: E402


def main() -> None:
    store = AvailabilityStore()
    created = store.seed_demo()
    print(f"Seeded {len(created)} booking(s):")
    for c in created:
        print(f"  {c.id}  {c.date} {c.time} party={c.party_size} {c.guest_name}")


if __name__ == "__main__":
    main()
