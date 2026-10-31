"""Turn data into text that sounds natural when read aloud by a TTS voice."""

from __future__ import annotations

import datetime as dt

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]  # fmt: skip


def say_time(t: dt.time) -> str:
    if t == dt.time(12, 0):
        return "noon"
    hour = t.hour % 12 or 12
    suffix = "AM" if t.hour < 12 else "PM"
    return f"{hour} {suffix}" if t.minute == 0 else f"{hour}:{t.minute:02d} {suffix}"


def say_date(d: dt.date, today: dt.date) -> str:
    if d == today:
        return "today"
    if d == today + dt.timedelta(days=1):
        return "tomorrow"
    return f"{_WEEKDAYS[d.weekday()]}, {_MONTHS[d.month - 1]} {d.day}"


def on_date(d: dt.date, today: dt.date) -> str:
    """'today', 'tomorrow' or 'on Friday, November 6' (reads naturally after a time)."""
    word = say_date(d, today)
    return word if word in ("today", "tomorrow") else f"on {word}"


def join_or(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + (", or " if len(items) > 2 else " or ") + items[-1]


def say_offers(offers: list[dt.datetime], today: dt.date) -> str:
    if len({o.date() for o in offers}) == 1:
        return f"{join_or([say_time(o.time()) for o in offers])} {on_date(offers[0].date(), today)}"
    return join_or([f"{say_date(o.date(), today)} at {say_time(o.time())}" for o in offers])


def say_digits(digits: str) -> str:
    return " ".join(digits)


def say_phone(phone: str) -> str:
    return f"{say_digits(phone[:4])}, {say_digits(phone[4:])}"
