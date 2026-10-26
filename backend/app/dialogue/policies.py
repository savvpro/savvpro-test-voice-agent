"""Business rules for when an appointment can be made.

Each check returns None when fine, or a short reason code the responses map to
a reply ("past", "closed", "lunch", ...).
"""

import datetime as dt

from app.clinic import BOOKING_WINDOW_DAYS, OPENING_HOURS, SLOT_MINUTES


def check_date(day: dt.date, today: dt.date) -> str | None:
    if day < today:
        return "date_past"
    if not OPENING_HOURS[day.weekday()]:
        return "date_closed"
    if day > today + dt.timedelta(days=BOOKING_WINDOW_DAYS):
        return "date_too_far"
    return None


def check_time(day: dt.date, at: dt.time, now: dt.datetime) -> str | None:
    """Can an appointment *start* at ``at`` on ``day``? (date assumed valid)"""
    periods = OPENING_HOURS[day.weekday()]
    if not periods:
        return "date_closed"
    if dt.datetime.combine(day, at) <= now:
        return "time_past"
    slot = dt.timedelta(minutes=SLOT_MINUTES)
    for start, end in periods:
        if start <= at and dt.datetime.combine(day, at) + slot <= dt.datetime.combine(day, end):
            return None
    if at < periods[0][0]:
        return "time_before_open"
    if at >= periods[-1][1] or dt.datetime.combine(day, at) + slot > dt.datetime.combine(
        day, periods[-1][1]
    ):
        return "time_after_close"
    return "time_lunch"
