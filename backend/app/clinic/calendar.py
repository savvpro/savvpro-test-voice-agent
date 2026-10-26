"""Brightside Dental's appointment book (in memory, fake data only).

Hours: Monday to Friday 9:00-17:00 with a 12:00-13:00 lunch break,
Saturday 9:00-13:00, closed Sunday. Appointments are 30 minutes. Some slots
are already taken, chosen deterministically so behaviour is repeatable.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

SLOT = timedelta(minutes=30)
HOURS = {  # weekday -> list of (open, close)
    0: [(time(9), time(12)), (time(13), time(17))],
    1: [(time(9), time(12)), (time(13), time(17))],
    2: [(time(9), time(12)), (time(13), time(17))],
    3: [(time(9), time(12)), (time(13), time(17))],
    4: [(time(9), time(12)), (time(13), time(17))],
    5: [(time(9), time(13))],
    6: [],
}
HOURS_TEXT = "Monday to Friday 9 AM to 5 PM, closed for lunch from 12 to 1, and Saturday 9 AM to 1 PM. We're closed on Sundays."
ADDRESS_TEXT = "We're at 1200 Maple Avenue, Suite 4, in Springfield, with free parking behind the building."
INSURANCE_TEXT = "We accept most PPO plans, including Delta Dental, Cigna, Aetna and MetLife, and we offer payment plans."
SERVICE_LABELS = {
    "cleaning": "cleaning",
    "checkup": "check-up",
    "filling": "filling",
    "whitening": "whitening",
    "consultation": "consultation",
    "emergency": "emergency visit",
}


@dataclass
class Booking:
    id: str
    name: str
    phone: str
    service: str
    start: datetime


@dataclass
class Calendar:
    today: date
    bookings: dict[str, Booking] = field(default_factory=dict)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1001))

    def __post_init__(self) -> None:
        if not self.bookings:
            # One existing appointment so callers can reschedule or cancel.
            demo = self.next_open_day(self.today + timedelta(days=2))
            self.add("Jordan Lee", "5550142233", "cleaning", datetime.combine(demo, time(10, 0)))

    # --- opening hours -------------------------------------------------
    def windows(self, day: date) -> list[tuple[time, time]]:
        return HOURS[day.weekday()]

    def is_open_day(self, day: date) -> bool:
        return bool(self.windows(day))

    def within_hours(self, start: datetime) -> bool:
        end = (start + SLOT).time()
        return start.minute in (0, 30) and any(
            o <= start.time() and end <= c for o, c in self.windows(start.date())
        )

    def next_open_day(self, day: date) -> date:
        while not self.is_open_day(day):
            day += timedelta(days=1)
        return day

    # --- availability --------------------------------------------------
    def _seeded_busy(self, start: datetime) -> bool:
        # Fake existing patients: a fixed pattern of taken slots.
        return (start.day + start.hour + start.minute // 30) % 4 == 0

    def is_free(self, start: datetime) -> bool:
        if not self.within_hours(start) or self._seeded_busy(start):
            return False
        return all(b.start != start for b in self.bookings.values())

    def slots(self, day: date) -> list[datetime]:
        out = []
        for open_, close in self.windows(day):
            t = datetime.combine(day, open_)
            while t + SLOT <= datetime.combine(day, close):
                out.append(t)
                t += SLOT
        return out

    def free_slots(self, day: date, after: datetime | None = None) -> list[datetime]:
        return [s for s in self.slots(day) if self.is_free(s) and (after is None or s > after)]

    def alternatives(self, wanted: datetime, now: datetime, count: int = 2) -> list[datetime]:
        """Nearest free slots to `wanted`: same day first, then the following days."""
        found: list[datetime] = []
        day = wanted.date()
        for _ in range(14):
            free = [s for s in self.free_slots(day) if s > now]
            free.sort(key=lambda s: abs((s - wanted).total_seconds()))
            found.extend(free[: count - len(found)])
            if len(found) >= count:
                break
            day += timedelta(days=1)
        return sorted(found)

    def earliest(self, now: datetime, count: int = 2) -> list[datetime]:
        found: list[datetime] = []
        day = now.date()
        for _ in range(14):
            found.extend(s for s in self.free_slots(day) if s > now)
            if len(found) >= count:
                return found[:count]
            day += timedelta(days=1)
        return found

    # --- bookings ------------------------------------------------------
    def add(self, name: str, phone: str, service: str, start: datetime) -> Booking:
        booking = Booking(f"BS-{next(self._ids)}", name, phone, service, start)
        self.bookings[booking.id] = booking
        return booking

    def find_by_phone(self, phone: str) -> Booking | None:
        upcoming = [b for b in self.bookings.values() if b.phone and phones_match(b.phone, phone)]
        return min(upcoming, key=lambda b: b.start) if upcoming else None

    def find_by_name(self, name: str) -> Booking | None:
        """Full name, or a first name that only one booking has."""
        wanted = name.lower().split()
        exact = [b for b in self.bookings.values() if b.name.lower().split() == wanted]
        if not exact and len(wanted) == 1:
            first = [b for b in self.bookings.values() if b.name.lower().split()[0] == wanted[0]]
            exact = first if len({b.name for b in first}) == 1 else []
        return min(exact, key=lambda b: b.start) if exact else None

    def cancel(self, booking_id: str) -> None:
        self.bookings.pop(booking_id, None)

    def move(self, booking_id: str, start: datetime) -> Booking:
        booking = self.bookings[booking_id]
        booking.start = start
        return booking


def phones_match(a: str, b: str) -> bool:
    """Same digits, allowing one side to carry a country code the other left off."""
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    return len(shorter) >= 7 and longer.endswith(shorter)


def say_time(t: datetime | time) -> str:
    value = t.time() if isinstance(t, datetime) else t
    hour = value.hour % 12 or 12
    suffix = "AM" if value.hour < 12 else "PM"
    return f"{hour}:{value.minute:02d} {suffix}" if value.minute else f"{hour} {suffix}"


def say_date(d: date, today: date) -> str:
    if d == today:
        return "today"
    if d == today + timedelta(days=1):
        return "tomorrow"
    return f"{d.strftime('%A')}, {d.strftime('%B')} {d.day}"


def say_slot(s: datetime, today: date) -> str:
    return f"{say_date(s.date(), today)} at {say_time(s)}"
