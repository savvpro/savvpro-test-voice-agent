"""Facts about the (fictional) clinic, shared by the seed data, policies and replies."""

from datetime import time

CLINIC_NAME = "Shifa Care Clinic"
CLINIC_ADDRESS = "45 Jasmine Road, Green Valley, Lahore"  # invented
SLOT_MINUTES = 20
BOOKING_WINDOW_DAYS = 30

# weekday() -> opening periods. Weekdays have a 13:00-14:00 lunch break,
# Saturday is a half day, Sunday is closed.
_WEEKDAY_HOURS = [(time(9), time(13)), (time(14), time(17))]
OPENING_HOURS: dict[int, list[tuple[time, time]]] = {
    0: _WEEKDAY_HOURS,
    1: _WEEKDAY_HOURS,
    2: _WEEKDAY_HOURS,
    3: _WEEKDAY_HOURS,
    4: _WEEKDAY_HOURS,
    5: [(time(9), time(13))],
    6: [],
}
