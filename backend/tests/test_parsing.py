from datetime import date, time

from app.parsing import parse_date, parse_dob, parse_time

TODAY = date(2026, 10, 26)  # Monday


def test_relative_dates() -> None:
    for text, want in [
        ("tomorrow", date(2026, 10, 27)),
        ("day after tomorrow", date(2026, 10, 28)),
        ("Friday", date(2026, 10, 30)),
        ("next Monday", date(2026, 11, 2)),
        ("next Tuesday", date(2026, 11, 3)),
        ("this Tuesday", date(2026, 10, 27)),
        ("the 14th", date(2026, 11, 14)),
        ("the fourteenth", date(2026, 11, 14)),
        ("the 30th", date(2026, 10, 30)),
        ("November 3rd", date(2026, 11, 3)),
        ("Nov 3", date(2026, 11, 3)),
        ("3rd of November", date(2026, 11, 3)),
        ("11/3", date(2026, 11, 3)),
        ("11/3/2026", date(2026, 11, 3)),
        ("2026-11-03", date(2026, 11, 3)),
        ("January 5", date(2027, 1, 5)),
    ]:
        assert parse_date(text, TODAY) == want, text
    assert parse_date("blah", TODAY) is None


def test_weekday_today() -> None:
    assert parse_date("Monday", TODAY) == date(2026, 10, 26)


def test_times() -> None:
    for text, want in [
        ("3pm", time(15, 0)),
        ("3:30 pm", time(15, 30)),
        ("15:00", time(15, 0)),
        ("half past three", time(15, 30)),
        ("quarter to four", time(15, 45)),
        ("quarter past four", time(16, 15)),
        ("3 o'clock", time(15, 0)),
        ("noon", time(12, 0)),
        ("in the morning", "morning"),
        ("this afternoon", "afternoon"),
        ("9 am", time(9, 0)),
        ("blah", None),
    ]:
        assert parse_time(text) == want, text


def test_bare_hour_is_pm() -> None:
    assert parse_time("at 3") == time(15, 0)
    assert parse_time("at 10") == time(10, 0)
    assert parse_time("at 12") == time(12, 0)


def test_dob() -> None:
    for text in ["March 4 1990", "03/04/1990", "4th of March 1990", "March 4th, 1990"]:
        assert parse_dob(text) == date(1990, 3, 4), text
    assert parse_dob("March 4") is None
    assert parse_dob("March 4 2999", TODAY) is None


def test_dob_dashes_and_unambiguous_day_first() -> None:
    assert parse_dob("03-04-1990") == date(1990, 3, 4)  # US month-day
    assert parse_dob("12-30-1990") == date(1990, 12, 30)
    assert parse_dob("30-12-1990") == date(1990, 12, 30)  # day > 12 can only be day-first
    assert parse_dob("30/12/1990") == date(1990, 12, 30)
    assert parse_dob("13-13-1990") is None
