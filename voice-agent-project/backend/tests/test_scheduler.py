import datetime as dt

from conftest import FRIDAY, MONDAY_8AM, SUNDAY, TOMORROW, Call


def test_sundays_are_closed():
    call = Call()
    assert call.scheduler.slot_times(SUNDAY) == []


def test_slot_grid_is_half_hourly_nine_to_four_thirty():
    slots = Call().scheduler.slot_times(TOMORROW)
    assert slots[0].time() == dt.time(9, 0) and slots[-1].time() == dt.time(16, 30) and len(slots) == 16


def test_busy_pattern_is_deterministic():
    a, b = Call(), Call()
    assert a.free_slots("dental", FRIDAY) == b.free_slots("dental", FRIDAY)


def test_book_then_slot_is_taken():
    call = Call()
    slot = call.free_slots("general", FRIDAY)[0]
    assert call.scheduler.book("Test Patient", "03211234567", "general", slot)
    assert not call.scheduler.is_free("general", slot)
    assert call.scheduler.book("Other Patient", "03221234567", "general", slot) is None


def test_off_grid_and_past_times_are_never_free():
    call = Call(now=dt.datetime(2026, 11, 2, 14, 0))
    assert not call.scheduler.is_free("general", dt.datetime(2026, 11, 3, 10, 15))
    assert not call.scheduler.is_free("general", dt.datetime(2026, 11, 2, 13, 0))


def test_alternatives_are_nearest_and_free():
    call = Call()
    busy = call.busy_slot("general", FRIDAY)
    alts = call.scheduler.alternatives("general", busy, n=3)
    assert len(alts) == 3 and alts == sorted(alts)
    assert all(call.scheduler.is_free("general", a) for a in alts)


def test_cancel_and_reschedule():
    call = Call()
    appt = call.scheduler.find_by_phone("03001234567")[0]
    target = call.free_slots("general", FRIDAY)[0]
    assert call.scheduler.reschedule(appt.id, target).start == target
    assert call.scheduler.cancel(appt.id)
    assert call.scheduler.find_by_phone("03001234567") == []
    assert not call.scheduler.cancel(appt.id)


def test_find_by_phone_ignores_past_appointments():
    call = Call()
    call.now = MONDAY_8AM + dt.timedelta(days=30)
    assert call.scheduler.find_by_phone("03001234567") == []
