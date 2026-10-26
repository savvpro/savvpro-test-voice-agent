"""Fake demo bookings so a new call already meets a half-full calendar. Fake data only."""
from datetime import datetime, time, timedelta

from app.services.booking import ClinicCalendar

FAKE_PATIENTS = [
    ("Demo Patient One", "03000000001", "checkup"),
    ("Demo Patient Two", "03000000002", "cleaning"),
    ("Demo Patient Three", "03000000003", "filling"),
]


def seed_calendar(calendar: ClinicCalendar, now: datetime) -> ClinicCalendar:
    """Book a few 'already taken' slots tomorrow (9:00, 9:30, 11:00) so the demo shows offers."""
    tomorrow = datetime.combine(now.date() + timedelta(days=1), time(9, 0))
    for (name, phone, service), offset_minutes in zip(FAKE_PATIENTS, (0, 30, 120)):
        slot = tomorrow + timedelta(minutes=offset_minutes)
        if not calendar.is_taken(slot):
            try:
                calendar.book(slot, name, phone, service)
            except Exception:
                pass
    return calendar
