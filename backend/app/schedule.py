"""In-memory fake clinic schedule. Mon-Fri, 30-minute slots from 9:00 to 16:30."""
from datetime import date, datetime, timedelta

SLOTS = [f"{h:02d}:{m:02d}" for h in range(9, 17) for m in (0, 30)]


def fmt_time(t):
    return datetime.strptime(t, "%H:%M").strftime("%I:%M %p").lstrip("0")


def fmt(d, t):
    return f"{datetime.fromisoformat(d):%A %d %B} at {fmt_time(t)}"


def _mins(t):
    return int(t[:2]) * 60 + int(t[3:])


class Schedule:
    def __init__(self, today, seed=True):
        self.b, self.n = {}, 0
        if seed:  # fake data: the next weekday is partly booked
            d = today + timedelta(1)
            while d.weekday() >= 5:
                d += timedelta(1)
            for name, t in (("Sam Demo", "10:00"), ("Jo Demo", "10:30")):
                self.book(name, d.isoformat(), t)

    def book(self, name, d, t):
        self.n += 1
        ref = f"APT-{1000 + self.n}"
        self.b[(d, t)] = (name, ref)
        return ref

    def cancel(self, key):
        self.b.pop(key, None)

    def find(self, name):
        return next((k for k, (n, _) in sorted(self.b.items()) if n.lower() == name.lower()), None)

    def check(self, d, t, today):
        """Returns None if free, otherwise 'past' | 'weekend' | 'hours' | 'taken'."""
        dd = date.fromisoformat(d)
        if dd < today:
            return "past"
        if dd.weekday() >= 5:
            return "weekend"
        if t not in SLOTS:
            return "hours"
        return "taken" if (d, t) in self.b else None

    def alternatives(self, d, t, n=3):
        free = [s for s in SLOTS if (d, s) not in self.b]
        return sorted(sorted(free, key=lambda s: abs(_mins(s) - _mins(t)))[:n])
