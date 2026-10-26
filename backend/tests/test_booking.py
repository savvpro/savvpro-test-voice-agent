from datetime import datetime, timedelta

import pytest

from app.services.booking import (
    ClinicCalendar,
    SlotTakenError,
    is_within_opening_hours,
)

# 2026-10-27 is a Tuesday, 2026-10-31 a Saturday, 2026-11-01 a Sunday.
TUESDAY_11 = datetime(2026, 10, 27, 11, 0)


def test_new_calendar_has_nothing_taken():
    assert not ClinicCalendar().is_taken(TUESDAY_11)


def test_booked_slot_is_taken_and_next_slot_is_free():
    calendar = ClinicCalendar()
    calendar.book(TUESDAY_11, "John Doe", "03001234567", "checkup")
    assert calendar.is_taken(TUESDAY_11)
    assert not calendar.is_taken(datetime(2026, 10, 27, 11, 30))


def test_booking_a_taken_slot_raises():
    calendar = ClinicCalendar()
    calendar.book(TUESDAY_11, "John Doe", "03001234567", "checkup")
    with pytest.raises(SlotTakenError):
        calendar.book(TUESDAY_11, "Jane Roe", "03007654321", "cleaning")


@pytest.mark.parametrize(
    "start, expected",
    [
        (datetime(2026, 10, 27, 17, 10), False),  # 5:10 PM is off the grid
        (datetime(2026, 10, 27, 9, 0, 30), False),  # 30 seconds past the hour
        (datetime(2026, 10, 27, 9, 30), True),
    ],
)
def test_is_on_grid(start, expected):
    assert ClinicCalendar().is_on_grid(start) is expected


def test_booking_on_sunday_raises_and_stores_nothing():
    calendar = ClinicCalendar()
    sunday = datetime(2026, 11, 1, 11, 0)
    with pytest.raises(ValueError):
        calendar.book(sunday, "John Doe", "03001234567", "checkup")
    assert not calendar.is_taken(sunday)


def test_booking_unknown_service_raises_and_stores_nothing():
    calendar = ClinicCalendar()
    with pytest.raises(ValueError):
        calendar.book(TUESDAY_11, "John Doe", "03001234567", "teeth whitening")
    assert not calendar.is_taken(TUESDAY_11)


def test_next_free_slots_skips_taken_slot_in_order():
    calendar = ClinicCalendar()
    calendar.book(TUESDAY_11, "John Doe", "03001234567", "checkup")
    slots = calendar.next_free_slots(TUESDAY_11, count=3)
    assert slots == [
        datetime(2026, 10, 27, 11, 30),
        datetime(2026, 10, 27, 12, 0),
        datetime(2026, 10, 27, 12, 30),
    ]


def test_next_free_slots_skips_closed_sunday_and_rounds_up():
    # Saturday 16:40 is off the grid; Saturday closes at 17:00, Sunday is closed.
    slots = ClinicCalendar().next_free_slots(datetime(2026, 10, 31, 16, 40), count=1)
    assert slots == [datetime(2026, 11, 2, 9, 0)]  # Monday 09:00


def test_next_free_slots_returns_empty_list_when_nothing_is_free():
    calendar = ClinicCalendar()
    start = datetime(2026, 10, 27, 9, 0)
    slot = start
    while slot < start + timedelta(days=15):  # fill every open slot for 15 days
        if is_within_opening_hours(slot):
            calendar.book(slot, "Fake Patient", "03000000000", "checkup")
        slot += timedelta(minutes=30)
    assert calendar.next_free_slots(start, count=3) == []


@pytest.mark.parametrize(
    "start, expected",
    [
        (datetime(2026, 10, 26, 9, 0), True),    # Monday, opening time
        (datetime(2026, 10, 27, 8, 59), False),  # before opening
        (datetime(2026, 10, 28, 16, 30), True),  # ends exactly at closing
        (datetime(2026, 10, 29, 16, 45), False),  # would end after closing
        (datetime(2026, 11, 1, 11, 0), False),   # Sunday
    ],
)
def test_opening_hours(start, expected):
    assert is_within_opening_hours(start) is expected
