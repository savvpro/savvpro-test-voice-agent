"""Booking service — slot availability, booking, releasing, and rebooking."""

from __future__ import annotations

from datetime import date, datetime

from app.data.interfaces import IParcelRepository
from app.models.parcel import DeliverySlot

# Period cutoff hours — same as in date_parser, kept here for the
# "is this period past?" check on today's slots.
_PERIOD_CUTOFFS: dict[str, int] = {
    "morning": 12,
    "afternoon": 17,
    "evening": 21,
}


def get_available_slots(
    repo: IParcelRepository,
    target_date: date,
    clock: datetime,
    period: str | None = None,
) -> list[DeliverySlot]:
    """Return available (non-full) slots for *target_date*.

    Filters out:
    - Slots where ``booked >= capacity``.
    - Slots that fall before the current clock time today (cutoff).
    - If *period* is specified, only returns that period.

    Args:
        repo: The parcel repository.
        target_date: The date to check.
        clock: Injected datetime — never reads system clock.
        period: Optional period filter.

    Returns:
        A list of available ``DeliverySlot`` objects.
    """
    all_slots = repo.list_slots(target_date, target_date)

    available: list[DeliverySlot] = []
    for slot in all_slots:
        # Skip full slots.
        if slot.booked >= slot.capacity:
            continue

        # Skip past periods on today.
        if slot.date == clock.date():
            cutoff = _PERIOD_CUTOFFS.get(slot.period, 24)
            if clock.hour >= cutoff:
                continue

        # Apply period filter.
        if period and slot.period != period:
            continue

        available.append(slot)

    return available


def find_nearest_available(
    repo: IParcelRepository,
    clock: datetime,
    exclude_date: date | None = None,
    period: str | None = None,
) -> DeliverySlot | None:
    """Find the nearest available slot across the 7-day window.

    Optionally excludes a specific date and/or filters by period.
    """
    from datetime import timedelta

    today = clock.date()
    for day_offset in range(7):
        check_date = today + timedelta(days=day_offset)
        if check_date == exclude_date:
            continue
        slots = get_available_slots(repo, check_date, clock, period=period)
        if slots:
            return slots[0]

    # If period specified and nothing found, try without period filter.
    if period:
        for day_offset in range(7):
            check_date = today + timedelta(days=day_offset)
            if check_date == exclude_date:
                continue
            slots = get_available_slots(repo, check_date, clock)
            if slots:
                return slots[0]

    return None


def book_slot(
    repo: IParcelRepository,
    slot_id: str,
    tracking_id: str,
) -> bool:
    """Book a delivery slot for a parcel.

    Returns ``True`` on success, ``False`` if the slot is full or not found.
    """
    return repo.book_slot(slot_id, tracking_id)


def release_slot(
    repo: IParcelRepository,
    slot_id: str,
    tracking_id: str,
) -> bool:
    """Release a previously booked slot.

    Returns ``True`` on success, ``False`` if the slot was not booked by
    this parcel.
    """
    return repo.release_slot(slot_id, tracking_id)


def rebook_slot(
    repo: IParcelRepository,
    old_slot_id: str,
    new_slot_id: str,
    tracking_id: str,
) -> bool:
    """Atomically release the old slot and book the new one.

    Returns ``False`` if the new slot is full (old slot remains unchanged).
    """
    return repo.rebook_slot(old_slot_id, new_slot_id, tracking_id)
