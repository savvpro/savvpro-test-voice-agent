"""Load JSON data files and generate the runtime slot grid.

All loader functions accept explicit paths or a ``clock`` so they can be
called deterministically from both the app lifespan hook and tests.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from app.models.parcel import (
    DeliverySlot,
    Parcel,
    Period,
    PickupPoint,
    SlotTemplate,
)


def load_parcels(data_dir: Path) -> list[Parcel]:
    """Read ``parcels.json`` and return validated Parcel objects."""
    path = data_dir / "parcels.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [Parcel.model_validate(item) for item in raw]


def load_pickup_points(data_dir: Path) -> list[PickupPoint]:
    """Read ``pickup_points.json`` and return validated PickupPoint objects."""
    path = data_dir / "pickup_points.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [PickupPoint.model_validate(item) for item in raw]


def _load_slot_template(data_dir: Path) -> SlotTemplate:
    """Read ``slots.json`` capacity template."""
    path = data_dir / "slots.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return SlotTemplate.model_validate(raw)


def generate_slots(template: SlotTemplate, clock: datetime) -> list[DeliverySlot]:
    """Build the 7-day slot grid (today → today + 6) from *template*.

    Args:
        template: Capacity template loaded from ``slots.json``.
        clock: Injected datetime; today is ``clock.date()``.

    Returns:
        A list of 21 ``DeliverySlot`` objects (7 days × 3 periods).
    """
    today = clock.date()
    # Index pre-booked overrides for O(1) lookup.
    pre_booked_map: dict[tuple[int, str], int] = {
        (pb.day_offset, pb.period.value): pb.booked
        for pb in template.pre_booked
    }

    slots: list[DeliverySlot] = []
    for offset in range(7):
        day = today + timedelta(days=offset)
        date_str = day.isoformat()
        for period in Period:
            slot_id = f"SLOT-{date_str}-{period.value}"
            booked = pre_booked_map.get((offset, period.value), 0)
            slots.append(
                DeliverySlot(
                    slot_id=slot_id,
                    date=day,
                    period=period,
                    capacity=template.default_capacity,
                    booked=booked,
                )
            )
    return slots


def load_slots(data_dir: Path, clock: datetime) -> list[DeliverySlot]:
    """Load the slot template and generate the full slot grid.

    Convenience wrapper that calls ``_load_slot_template`` then
    ``generate_slots``.
    """
    template = _load_slot_template(data_dir)
    return generate_slots(template, clock)
