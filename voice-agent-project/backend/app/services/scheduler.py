"""Fake clinic schedule (in memory). All patient data here is invented."""

from __future__ import annotations

import datetime as dt
import threading
import zlib
from collections.abc import Callable

from ..brain.models import Appointment

OPEN_TIME = dt.time(9, 0)
LAST_SLOT = dt.time(16, 30)
SLOT_MINUTES = 30
HORIZON_DAYS = 30
BUSY_PERCENT = 35  # share of slots pre-filled by "other patients"
DAYPARTS = {
    "morning": (dt.time(9, 0), dt.time(11, 30)),
    "afternoon": (dt.time(12, 0), dt.time(16, 30)),
    "evening": (dt.time(15, 30), dt.time(16, 30)),  # the clinic closes at 5 PM
}


class Scheduler:
    def __init__(self, clock: Callable[[], dt.datetime]):
        self._clock = clock
        self._lock = threading.Lock()
        self._bookings: dict[int, Appointment] = {}
        self._next_id = 1001
        self._seed_demo_patients()

    # ---- helpers -------------------------------------------------------------
    def now(self) -> dt.datetime:
        return self._clock()

    @staticmethod
    def is_open_day(day: dt.date) -> bool:
        return day.weekday() != 6  # closed on Sundays

    def slot_times(self, day: dt.date) -> list[dt.datetime]:
        if not self.is_open_day(day):
            return []
        out, cur = [], dt.datetime.combine(day, OPEN_TIME)
        end = dt.datetime.combine(day, LAST_SLOT)
        while cur <= end:
            out.append(cur)
            cur += dt.timedelta(minutes=SLOT_MINUTES)
        return out

    @staticmethod
    def _seeded_busy(specialty: str, start: dt.datetime) -> bool:
        return zlib.crc32(f"{specialty}|{start.isoformat()}".encode()) % 100 < BUSY_PERCENT

    def _booked(self, specialty: str, start: dt.datetime) -> bool:
        return any(a.specialty == specialty and a.start == start for a in self._bookings.values())

    def _seed_demo_patients(self) -> None:
        day = self.now().date() + dt.timedelta(days=1)
        while not self.is_open_day(day):
            day += dt.timedelta(days=1)
        for name, phone, specialty, hour in (
            ("Sara Malik", "03001234567", "general", 11),
            ("Ali Raza", "03111234567", "dental", 14),
        ):
            self._add(name, phone, specialty, dt.datetime.combine(day, dt.time(hour, 0)))

    def _add(self, name: str, phone: str, specialty: str, start: dt.datetime) -> Appointment:
        appt = Appointment(self._next_id, name, phone, specialty, start)
        self._bookings[appt.id] = appt
        self._next_id += 1
        return appt

    # ---- queries -------------------------------------------------------------
    def is_free(self, specialty: str, start: dt.datetime) -> bool:
        on_grid = start.minute % SLOT_MINUTES == 0 and start.second == 0
        in_hours = OPEN_TIME <= start.time() <= LAST_SLOT
        return (
            on_grid
            and in_hours
            and self.is_open_day(start.date())
            and start > self.now()
            and not self._seeded_busy(specialty, start)
            and not self._booked(specialty, start)
        )

    def free_slots(self, specialty: str, day: dt.date) -> list[dt.datetime]:
        return [s for s in self.slot_times(day) if self.is_free(specialty, s)]

    def alternatives(self, specialty: str, near: dt.datetime, n: int = 3, window_days: int = 7) -> list[dt.datetime]:
        """The n free slots closest in time to `near`, returned in chronological order."""
        candidates: list[dt.datetime] = []
        for offset in range(-2, window_days + 1):
            day = near.date() + dt.timedelta(days=offset)
            if day < self.now().date():
                continue
            candidates.extend(self.free_slots(specialty, day))
        candidates.sort(key=lambda s: abs(s - near))
        return sorted(candidates[:n])

    def find_by_phone(self, phone: str) -> list[Appointment]:
        now = self.now()
        found = [a for a in self._bookings.values() if a.phone == phone and a.start > now]
        return sorted(found, key=lambda a: a.start)

    # ---- commands ------------------------------------------------------------
    def book(self, name: str, phone: str, specialty: str, start: dt.datetime) -> Appointment | None:
        with self._lock:
            if not self.is_free(specialty, start):
                return None
            return self._add(name, phone, specialty, start)

    def cancel(self, appointment_id: int) -> bool:
        with self._lock:
            return self._bookings.pop(appointment_id, None) is not None

    def reschedule(self, appointment_id: int, start: dt.datetime) -> Appointment | None:
        with self._lock:
            appt = self._bookings.get(appointment_id)
            if appt is None or not self.is_free(appt.specialty, start):
                return None
            appt.start = start
            return appt
