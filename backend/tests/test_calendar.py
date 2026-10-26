from datetime import datetime, time, timedelta

from app.clinic.calendar import phones_match, say_slot


def test_hours(calendar):
    assert calendar.within_hours(datetime(2026, 10, 27, 9, 0))
    assert not calendar.within_hours(datetime(2026, 10, 27, 12, 0))  # lunch
    assert not calendar.within_hours(datetime(2026, 10, 27, 16, 45))  # not on the half hour
    assert not calendar.within_hours(datetime(2026, 10, 31, 13, 0))  # Saturday closes at 1
    assert not calendar.is_open_day(datetime(2026, 11, 1).date())  # Sunday


def test_demo_booking_exists(calendar):
    booking = calendar.find_by_phone("5550142233")
    assert booking and booking.name == "Jordan Lee"
    assert not calendar.is_free(booking.start)


def test_alternatives_are_free_and_in_the_future(calendar, now):
    wanted = datetime(2026, 10, 27, 10, 0)
    alts = calendar.alternatives(wanted, now)
    assert len(alts) == 2
    assert all(calendar.is_free(a) and a > now for a in alts)


def test_earliest_after_now(calendar, now):
    first = calendar.earliest(now)[0]
    assert first > now and first - now < timedelta(days=1)


def test_add_move_cancel(calendar):
    start = datetime(2026, 10, 27, 14, 30)
    b = calendar.add("Test Person", "5550000000", "cleaning", start)
    assert not calendar.is_free(start)
    calendar.move(b.id, datetime(2026, 10, 27, 15, 30))
    assert calendar.bookings[b.id].start.time() == time(15, 30)
    calendar.cancel(b.id)
    assert b.id not in calendar.bookings


def test_find_by_name_and_phone(calendar):
    assert calendar.find_by_name("jordan lee").id == "BS-1001"
    assert calendar.find_by_name("Jordan").id == "BS-1001"  # first name, only one Jordan
    assert calendar.find_by_name("Taylor Smith") is None
    assert calendar.find_by_phone("15550142233").id == "BS-1001"  # with a country code
    assert calendar.find_by_phone("") is None


def test_first_name_must_be_unique(calendar):
    calendar.add("Jordan Park", "", "filling", datetime(2026, 10, 27, 9, 0))
    assert calendar.find_by_name("jordan") is None
    assert calendar.find_by_name("jordan park").name == "Jordan Park"


def test_phones_match():
    assert phones_match("5551234567", "15551234567")
    assert not phones_match("5551234567", "5551234568")
    assert not phones_match("4567", "5551234567")  # too short to trust


def test_say_slot(now):
    assert say_slot(datetime(2026, 10, 27, 15, 30), now.date()) == "tomorrow at 3:30 PM"
    assert say_slot(datetime(2026, 10, 30, 9, 0), now.date()) == "Friday, October 30 at 9 AM"
