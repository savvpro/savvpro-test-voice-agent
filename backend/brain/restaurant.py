"""
Fake restaurant data — operating hours, tables, and an in-memory bookings store.

NO real customer data. NO database. Just enough state for the demo to feel real.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Operating hours per weekday (0 = Monday, 6 = Sunday).
# Open for lunch 11:30-14:00 and dinner 17:00-22:00. Closed Mondays.
# ---------------------------------------------------------------------------
OPERATING_HOURS: Dict[int, List[Tuple[str, str]]] = {
    0: [],  # Monday — closed
    1: [("11:30", "14:00"), ("17:00", "22:00")],
    2: [("11:30", "14:00"), ("17:00", "22:00")],
    3: [("11:30", "14:00"), ("17:00", "22:00")],
    4: [("11:30", "14:00"), ("17:00", "22:00")],
    5: [("17:00", "23:00")],  # Saturday dinner only, late close
    6: [("12:00", "21:00")],  # Sunday continuous
}

RESTAURANT_NAME = "The Copper Spoon"
RESTAURANT_PHONE = "(555) 010-2200"
RESTAURANT_ADDRESS = "482 Brass Street, Downtown"
RESTAURANT_CUISINE = "Modern European, with vegetarian and vegan options"

# Tables: id -> max seats. We pick the smallest table that fits the party.
TABLES: Dict[int, int] = {
    1: 2, 2: 2, 3: 4, 4: 4, 5: 4,
    6: 6, 7: 8, 8: 10,
}

# A booking occupies the table for 2 hours starting on the half hour.
BOOKING_DURATION_MIN = 120
SLOT_GRANULARITY_MIN = 30


@dataclass
class Booking:
    booking_id: str
    table_id: int
    date: str       # YYYY-MM-DD
    time: str       # HH:MM
    party_size: int
    name: str
    phone: str

    def __repr__(self) -> str:
        return f"<Booking {self.booking_id} {self.date} {self.time} p{self.party_size} {self.name}>"


# ---------------------------------------------------------------------------
# In-memory booking store. Seed with a few bookings so availability checks
# actually have something to fail against.
# ---------------------------------------------------------------------------
@dataclass
class BookingStore:
    bookings: Dict[str, Booking] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._seed()

    def reset(self) -> None:
        """Clear all bookings and reseed. Used by tests to avoid cross-test pollution."""
        self.bookings.clear()
        self._seed()

    def _seed(self) -> None:
        today = date.today()
        soon = (today + timedelta(days=1)).isoformat()
        later = (today + timedelta(days=3)).isoformat()
        seed = [
            ("B-1001", 3, soon, "19:00", 4, "Patel", "5550100001"),
            ("B-1002", 6, soon, "20:00", 6, "Nguyen", "5550100002"),
            ("B-1003", 1, later, "18:30", 2, "Garcia", "5550100003"),
            ("B-1004", 4, later, "19:30", 4, "Kowalski", "5550100004"),
        ]
        for b in seed:
            self.bookings[b[0]] = Booking(*b)

    # ------------------------------------------------------------------
    def is_open(self, d: date) -> bool:
        return bool(OPERATING_HOURS.get(d.weekday()))

    def opening_windows(self, d: date) -> List[Tuple[str, str]]:
        return list(OPERATING_HOURS.get(d.weekday(), []))

    def _table_booked(self, table_id: int, d: str, start: str) -> bool:
        """True if the table is booked at any point overlapping [start, start+duration)."""
        start_dt = datetime.combine(date.fromisoformat(d), time.fromisoformat(start))
        end_dt = start_dt + timedelta(minutes=BOOKING_DURATION_MIN)
        for b in self.bookings.values():
            if b.table_id != table_id or b.date != d:
                continue
            b_start = datetime.combine(date.fromisoformat(b.date), time.fromisoformat(b.time))
            b_end = b_start + timedelta(minutes=BOOKING_DURATION_MIN)
            if start_dt < b_end and b_start < end_dt:
                return True
        return False

    def _pick_table(self, party_size: int) -> Optional[int]:
        """Smallest table that fits the party."""
        for tid, seats in sorted(TABLES.items(), key=lambda kv: kv[1]):
            if seats >= party_size:
                return tid
        return None

    def is_available(self, d: str, t: str, party_size: int) -> Tuple[bool, str]:
        """Check if the requested slot is bookable. Returns (ok, reason)."""
        try:
            target_date = date.fromisoformat(d)
            target_time = time.fromisoformat(t)
        except ValueError:
            return False, "I couldn't parse that date or time."

        if not self.is_open(target_date):
            weekday_name = target_date.strftime("%A")
            return False, f"We're closed on {weekday_name}s. Could you try another day?"

        # Check the time falls inside an opening window
        windows = self.opening_windows(target_date)
        request_minutes = target_time.hour * 60 + target_time.minute
        in_window = False
        for opens, closes in windows:
            oh, om = map(int, opens.split(":"))
            ch, cm = map(int, closes.split(":"))
            if oh * 60 + om <= request_minutes <= ch * 60 + cm - BOOKING_DURATION_MIN:
                in_window = True
                break
        if not in_window:
            windows_human = ", ".join(f"{a}–{b}" for a, b in windows) or "closed"
            return False, f"We're not seating at that time. Our hours that day are {windows_human}."

        if party_size > max(TABLES.values()):
            return False, f"Unfortunately we can't seat a party of {party_size} — our largest table is for {max(TABLES.values())}."

        table_id = self._pick_table(party_size)
        if table_id is None:
            return False, "We don't have a table that fits your party."

        if self._table_booked(table_id, d, t):
            return False, "I'm sorry, that time is already taken."

        return True, f"Table {table_id} is available."

    def suggest_alternatives(self, d: str, party_size: int, requested_time: str, limit: int = 4) -> List[str]:
        """Return a list of available slot times for the given date & party size."""
        try:
            target_date = date.fromisoformat(d)
        except ValueError:
            return []
        if not self.is_open(target_date):
            return []

        windows = self.opening_windows(target_date)
        suggestions: List[str] = []
        for opens, closes in windows:
            oh, om = map(int, opens.split(":"))
            ch, cm = map(int, closes.split(":"))
            cur = oh * 60 + om
            end = ch * 60 + cm - BOOKING_DURATION_MIN
            while cur <= end:
                t_str = f"{cur // 60:02d}:{cur % 60:02d}"
                ok, _ = self.is_available(d, t_str, party_size)
                if ok:
                    suggestions.append(t_str)
                cur += SLOT_GRANULARITY_MIN
        # Prefer slots close to the requested time
        try:
            rh, rm = map(int, requested_time.split(":"))
            req_minutes = rh * 60 + rm
        except (ValueError, AttributeError):
            req_minutes = 18 * 60
        suggestions.sort(key=lambda s: abs(int(s.split(":")[0]) * 60 + int(s.split(":")[1]) - req_minutes))
        return suggestions[:limit]

    def create_booking(self, d: str, t: str, party_size: int, name: str, phone: str) -> Booking:
        ok, reason = self.is_available(d, t, party_size)
        if not ok:
            raise ValueError(reason)
        table_id = self._pick_table(party_size)
        booking_id = f"B-{len(self.bookings) + 2000:04d}"
        booking = Booking(
            booking_id=booking_id,
            table_id=table_id,
            date=d, time=t, party_size=party_size,
            name=name, phone=phone,
        )
        self.bookings[booking_id] = booking
        return booking

    def cancel_booking(self, booking_id: str) -> bool:
        return self.bookings.pop(booking_id, None) is not None


# Singleton store shared by all sessions.
STORE = BookingStore()
