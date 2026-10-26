"""A tiny in-memory appointment book with fake availability (no real data)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

WEEKDAY_HOURS = [9, 10, 11, 13, 14, 15, 16]   # lunch break 12-13, closes at 17:00
SATURDAY_HOURS = [9, 10, 11]                   # Saturday: 9 to 12
HOURS_TEXT = ("We're open nine to twelve and one to five, Monday to Friday, "
              "and nine to twelve on Saturdays. We're closed on Sundays.")

PERIODS = {
    "morning": lambda h: h < 12,
    "afternoon": lambda h: 12 <= h < 17,
    "evening": lambda h: h >= 15,   # clinic closes at five, so "evening" = latest slots
}


@dataclass(frozen=True)
class Appointment:
    id: str
    name: str
    service: str
    day: date
    time: time


class Schedule:
    def __init__(self) -> None:
        self._appts: dict[str, Appointment] = {}
        self._counter = 1000

    # ----- rules about the calendar
    @staticmethod
    def hours_for(d: date) -> list[int]:
        if d.weekday() == 6:
            return []
        return SATURDAY_HOURS if d.weekday() == 5 else WEEKDAY_HOURS

    @staticmethod
    def day_problem(d: date, today: date, window_days: int) -> str | None:
        if d < today:
            return "past"
        if d.weekday() == 6:
            return "closed"
        if (d - today).days > window_days:
            return "too_far"
        return None

    @staticmethod
    def _busy_by_default(d: date, hour: int) -> bool:
        """Fake 'already booked' pattern so the demo has realistic gaps."""
        return (d.toordinal() + hour) % 4 == 0

    def is_free(self, d: date, t: time) -> bool:
        if t.minute != 0 or t.hour not in self.hours_for(d):
            return False
        if self._busy_by_default(d, t.hour):
            return False
        return not any(a.day == d and a.time == t for a in self._appts.values())

    def check(self, d: date, t: time, now: datetime) -> tuple[bool, str | None]:
        if d.weekday() == 6:
            return False, "closed"
        if datetime.combine(d, t) <= now:
            return False, "past"
        if t.hour not in self.hours_for(d):
            return False, "outside_hours"
        if t.minute != 0:
            return False, "off_grid"
        if not self.is_free(d, t):
            return False, "taken"
        return True, None

    # ----- searching
    def free_slots(self, d: date, now: datetime, period: str | None = None) -> list[time]:
        out = []
        for h in self.hours_for(d):
            t = time(h)
            if datetime.combine(d, t) <= now or not self.is_free(d, t):
                continue
            if period and not PERIODS[period](h):
                continue
            out.append(t)
        return out

    def nearest_free(self, d: date, wanted: time, now: datetime, limit: int = 3) -> list[time]:
        wanted_min = wanted.hour * 60 + wanted.minute
        slots = sorted(self.free_slots(d, now), key=lambda s: abs(s.hour * 60 - wanted_min))
        return sorted(slots[:limit])

    def next_available(self, after: date, now: datetime, limit: int = 3,
                       period: str | None = None, horizon: int = 21) -> tuple[date, list[time]] | None:
        for i in range(1, horizon + 1):
            d = after + timedelta(days=i)
            slots = self.free_slots(d, now, period)
            if slots:
                return d, slots[:limit]
        return None

    # ----- bookings
    def book(self, name: str, service: str, d: date, t: time) -> Appointment:
        self._counter += 1
        appt = Appointment(f"BS{self._counter}", name, service, d, t)
        self._appts[appt.id] = appt
        return appt

    def cancel(self, appt_id: str) -> bool:
        return self._appts.pop(appt_id, None) is not None

    def find_by_name(self, name: str, today: date) -> list[Appointment]:
        wanted = set(name.lower().split())
        found = [a for a in self._appts.values()
                 if a.day >= today and wanted and wanted <= set(a.name.lower().split())]
        return sorted(found, key=lambda a: (a.day, a.time))


def seed_demo(schedule: Schedule, today: date) -> Appointment:
    """One fake appointment so the cancel / reschedule flows can be demoed."""
    d = today + timedelta(days=2)
    while True:
        slots = schedule.free_slots(d, datetime.combine(today, time(0)))
        if slots:
            return schedule.book("Sara Khan", "cleaning", d, slots[0])
        d += timedelta(days=1)
