from datetime import date, datetime, time

import pytest

from app.dialogue.policies import check_date, check_time

TODAY = date(2030, 1, 9)  # Wednesday
NOW = datetime(2030, 1, 9, 10, 0)
FRIDAY = date(2030, 1, 11)
SATURDAY = date(2030, 1, 12)


@pytest.mark.parametrize(
    ("day", "problem"),
    [
        (TODAY, None),
        (FRIDAY, None),
        (SATURDAY, None),
        (date(2030, 2, 8), None),  # exactly 30 days ahead
        (date(2030, 1, 8), "date_past"),
        (date(2030, 1, 13), "date_closed"),  # Sunday
        (date(2030, 2, 9), "date_too_far"),
    ],
)
def test_check_date(day, problem):
    assert check_date(day, TODAY) == problem


@pytest.mark.parametrize(
    ("day", "at", "problem"),
    [
        (FRIDAY, time(9), None),
        (FRIDAY, time(12, 40), None),  # last morning slot
        (FRIDAY, time(14), None),
        (FRIDAY, time(16, 40), None),  # last slot of the day
        (FRIDAY, time(8, 30), "time_before_open"),
        (FRIDAY, time(16, 50), "time_after_close"),  # would run past 17:00
        (FRIDAY, time(19), "time_after_close"),
        (FRIDAY, time(13), "time_lunch"),
        (FRIDAY, time(13, 30), "time_lunch"),
        (FRIDAY, time(12, 50), "time_lunch"),  # would run into lunch
        (SATURDAY, time(12, 40), None),
        (SATURDAY, time(15), "time_after_close"),
        (TODAY, time(9, 40), "time_past"),
        (TODAY, time(11), None),
        (date(2030, 1, 13), time(10), "date_closed"),
    ],
)
def test_check_time(day, at, problem):
    assert check_time(day, at, NOW) == problem
