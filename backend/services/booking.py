"""Booking service with simulated restaurant database.

Uses fake in-memory data. No real personal information is stored.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, time, timedelta
from typing import Dict, List, Optional, Tuple

from models.booking import Booking, BookingStatus
import config

logger = logging.getLogger(__name__)


class BookingService:
    """Manages table availability and confirmed bookings.

    Simulates a restaurant with a fixed number of tables per time slot.
    """

    def __init__(self) -> None:
        # Slot occupancy: (date_iso, time_iso) → count of booked tables
        self._slots: Dict[Tuple[str, str], int] = defaultdict(int)
        # Confirmed bookings
        self._bookings: List[Booking] = []

        # Pre-seed some fake bookings for realism
        self._seed_fake_bookings()

    def check_availability(
        self, book_date: date, book_time: time, party_size: int
    ) -> bool:
        """Return True if a table is available for the given slot."""
        key = (book_date.isoformat(), book_time.isoformat())
        current = self._slots[key]
        available = current < config.TABLES_PER_SLOT
        logger.info(
            "Availability check: %s %s — %d/%d tables booked → %s",
            book_date, book_time, current, config.TABLES_PER_SLOT,
            "available" if available else "full",
        )
        return available

    def find_alternative(
        self, book_date: date, book_time: time, party_size: int
    ) -> Optional[Tuple[date, time]]:
        """Suggest an alternative slot near the requested one.

        Tries adjacent hours on the same day first, then the next day.
        """
        # Try ±1 and ±2 hours on the same day
        for delta in [1, -1, 2, -2]:
            alt_hour = book_time.hour + delta
            if config.OPENING_HOUR <= alt_hour < config.CLOSING_HOUR:
                alt_time = time(alt_hour, book_time.minute)
                if self.check_availability(book_date, alt_time, party_size):
                    return (book_date, alt_time)

        # Try same time on the next 3 days
        for day_delta in range(1, 4):
            alt_date = book_date + timedelta(days=day_delta)
            if self.check_availability(alt_date, book_time, party_size):
                return (alt_date, book_time)

        return None

    def save_booking(self, booking: Booking) -> None:
        """Confirm and persist a booking."""
        booking.status = BookingStatus.CONFIRMED
        self._bookings.append(booking)

        if booking.date and booking.time:
            key = (booking.date.isoformat(), booking.time.isoformat())
            self._slots[key] += 1

        logger.info("Booking saved: %s", booking.summary())

    def get_bookings(self) -> List[Booking]:
        """Return all confirmed bookings."""
        return [b for b in self._bookings if b.status == BookingStatus.CONFIRMED]

    def _seed_fake_bookings(self) -> None:
        """Pre-populate some time slots so availability checks are realistic."""
        today = date.today()
        # Fill up Friday 7pm and Saturday 8pm (popular slots)
        for day_offset in range(7):
            d = today + timedelta(days=day_offset)
            if d.weekday() == 4:  # Friday
                key = (d.isoformat(), time(19, 0).isoformat())
                self._slots[key] = config.TABLES_PER_SLOT  # fully booked
            if d.weekday() == 5:  # Saturday
                key = (d.isoformat(), time(20, 0).isoformat())
                self._slots[key] = config.TABLES_PER_SLOT - 1  # almost full
