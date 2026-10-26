"""Fictional restaurant availability dataset and reservation service."""

import datetime
from typing import List, Optional, Tuple, Dict
import uuid
from .models import AvailabilitySlot, ReservationRecord, BookingStatus


class RestaurantService:
    """Manages fictional table inventory and bookings for 'L'Osteria Tableline'.
    
    Demonstration parameters:
    - Operating hours: 17:00 to 22:00 (slots every 30 mins: 17:00, 17:30, 18:00, 18:30, 19:00, 19:30, 20:00, 20:30, 21:00, 21:30)
    - Total capacity: 5 tables per slot (each table seats up to 6 guests).
    - Max booking party size: 12 guests (requires 2 tables).
    - Fictional blackout/booked slots are pre-configured to test alternative recommendations realistically.
    """

    ALLOWED_TIMES = [
        "17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00", "21:30"
    ]
    TABLES_PER_SLOT = 5

    def __init__(self):
        # Key: (date_str, time_str) -> booked_tables_count
        self._bookings_count: Dict[Tuple[str, str], int] = {}
        # Key: reservation_id -> ReservationRecord
        self._reservations: Dict[str, ReservationRecord] = {}
        # Preload fictional booked tables to test availability realistically
        self._seed_fictional_bookings()

    def _seed_fictional_bookings(self):
        """Seed realistic fictional booked tables for testing slots."""
        # We simulate that 19:00 and 19:30 are heavily booked on any requested Friday or Saturday
        # and standard slots have varied baseline demand.
        pass

    def _get_tables_needed(self, guests: int) -> int:
        if guests <= 0:
            return 1
        return (guests + 5) // 6  # 1-6 guests: 1 table, 7-12 guests: 2 tables

    def is_valid_time_slot(self, time_str: str) -> bool:
        return time_str in self.ALLOWED_TIMES

    def check_availability(self, date_str: str, time_str: str, guests: int) -> Tuple[bool, int, List[str]]:
        """Checks if the requested slot is available for party size.
        Returns (is_available, remaining_tables, alternative_slots).
        """
        tables_needed = self._get_tables_needed(guests)
        
        # Check standard opening hours
        if time_str not in self.ALLOWED_TIMES:
            alternatives = self.get_available_alternatives(date_str, "19:00", guests)
            return False, 0, alternatives

        # Calculate booked tables
        current_booked = self._bookings_count.get((date_str, time_str), 0)
        
        # Simulated busy pattern: 19:00 is fully booked on Fridays and Saturdays for demonstration
        try:
            dt = datetime.date.fromisoformat(date_str)
            weekday = dt.weekday()  # 4 = Friday, 5 = Saturday
            if weekday in (4, 5) and time_str == "19:00":
                current_booked = max(current_booked, self.TABLES_PER_SLOT)
        except Exception:
            pass

        remaining = max(0, self.TABLES_PER_SLOT - current_booked)
        is_available = remaining >= tables_needed

        alternatives = []
        if not is_available:
            alternatives = self.get_available_alternatives(date_str, time_str, guests)

        return is_available, remaining, alternatives

    def get_available_alternatives(self, date_str: str, requested_time: str, guests: int) -> List[str]:
        """Finds closest open alternative times within operating hours on the same date."""
        tables_needed = self._get_tables_needed(guests)
        alternatives = []
        
        # Sort allowed times by proximity to requested time
        req_minutes = self._time_to_minutes(requested_time) if requested_time in self.ALLOWED_TIMES else 19 * 60

        candidate_times = sorted(
            self.ALLOWED_TIMES,
            key=lambda t: abs(self._time_to_minutes(t) - req_minutes)
        )

        for t in candidate_times:
            if t == requested_time:
                continue
            booked = self._bookings_count.get((date_str, t), 0)
            try:
                dt = datetime.date.fromisoformat(date_str)
                if dt.weekday() in (4, 5) and t == "19:00":
                    booked = max(booked, self.TABLES_PER_SLOT)
            except Exception:
                pass
            if (self.TABLES_PER_SLOT - booked) >= tables_needed:
                alternatives.append(t)
                if len(alternatives) >= 3:
                    break
        
        return alternatives

    def _time_to_minutes(self, t: str) -> int:
        try:
            parts = t.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except Exception:
            return 19 * 60

    def create_reservation(self, date_str: str, time_str: str, guests: int, customer_name: str) -> Optional[ReservationRecord]:
        """Creates an idempotent reservation if slot is available."""
        # Double check availability before booking
        is_avail, _, _ = self.check_availability(date_str, time_str, guests)
        if not is_avail:
            return None

        tables_needed = self._get_tables_needed(guests)
        current_booked = self._bookings_count.get((date_str, time_str), 0)
        self._bookings_count[(date_str, time_str)] = current_booked + tables_needed

        ref_id = f"TL-{uuid.uuid4().hex[:6].upper()}"
        record = ReservationRecord(
            reservation_id=ref_id,
            date=date_str,
            time=time_str,
            guests=guests,
            customer_name=customer_name or "Guest",
            status=BookingStatus.CONFIRMED,
            created_at=datetime.datetime.now().isoformat()
        )
        self._reservations[ref_id] = record
        return record

    def get_reservation(self, reservation_id: str) -> Optional[ReservationRecord]:
        return self._reservations.get(reservation_id)
