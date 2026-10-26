"""Domain models for parcels, delivery slots, and pickup points.

These Pydantic models serve double duty:
1. Validate data loaded from the JSON files at startup.
2. Act as the in-memory data structures the repository operates on.
"""

from __future__ import annotations

import enum
from datetime import date

from pydantic import BaseModel, Field

# ── Enums ─────────────────────────────────────────────────────────────

class ParcelStatus(str, enum.Enum):
    """Lifecycle status of a parcel."""

    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    FAILED_ATTEMPT = "failed_attempt"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED_TO_SENDER = "returned_to_sender"


class Period(str, enum.Enum):
    """Time-of-day delivery window."""

    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


# ── Parcel ────────────────────────────────────────────────────────────

class Parcel(BaseModel):
    """A parcel in the REDELIVER system.

    ``phone_failures`` and ``locked`` are runtime-only fields (not in JSON).
    ``recipient_name`` is for internal logging only — never expose to the
    caller before verification.
    """

    tracking_id: str
    phone_last4: str
    recipient_name: str
    status: ParcelStatus
    current_slot_id: str | None = None

    # Runtime-only fields (not in parcels.json)
    phone_failures: int = Field(default=0, exclude=True)
    locked: bool = Field(default=False, exclude=True)


# ── Delivery slot ─────────────────────────────────────────────────────

class DeliverySlot(BaseModel):
    """A bookable delivery time window on a specific date."""

    slot_id: str
    date: date
    period: Period
    capacity: int
    booked: int = 0

    @property
    def available(self) -> int:
        """Number of remaining bookable places."""
        return max(self.capacity - self.booked, 0)

    @property
    def is_full(self) -> bool:
        return self.booked >= self.capacity


# ── Pickup point ──────────────────────────────────────────────────────

class PickupPoint(BaseModel):
    """A physical location where a caller can collect a parcel."""

    point_id: str
    name: str
    address: str
    selection_aliases: list[str] = Field(default_factory=list)
    open_days: list[str]
    open_hours: str

    def is_open_on(self, day: date) -> bool:
        """Return True if this point is open on the given day."""
        weekday_name = day.strftime("%A").lower()
        return weekday_name in self.open_days


# ── Slot template (for loading slots.json) ────────────────────────────

class PreBookedEntry(BaseModel):
    """One pre-booked override inside ``slots.json``."""

    day_offset: int
    period: Period
    booked: int


class SlotTemplate(BaseModel):
    """The capacity template read from ``slots.json``.

    The actual slot grid is generated at runtime relative to the injected
    clock; this template only defines the default capacity per period and
    which day offsets have pre-booked slots.
    """

    default_capacity: int = 3
    pre_booked: list[PreBookedEntry] = Field(default_factory=list)
