"""Unit tests — config.py."""

from __future__ import annotations

from app.config import Settings


def test_defaults() -> None:
    s = Settings()
    assert s.clinic_name == "BrightSmile Dental Clinic"
    assert s.clinic_open_hour == 9
    assert s.clinic_close_hour == 17
    assert s.clinic_slot_minutes == 30
    assert 0 in s.clinic_open_weekdays
    assert 6 not in s.clinic_open_weekdays  # Sunday closed by default


def test_database_url_default() -> None:
    s = Settings()
    assert s.database_url.startswith("sqlite")


def test_cors_origins_comma_string() -> None:
    s = Settings(cors_origins="http://a.com,http://b.com")  # type: ignore[arg-type]
    assert s.cors_origins == ["http://a.com", "http://b.com"]


def test_clinic_open_weekdays_comma_string() -> None:
    s = Settings(clinic_open_weekdays="0,1,2,3")  # type: ignore[arg-type]
    assert s.clinic_open_weekdays == [0, 1, 2, 3]


def test_max_turns() -> None:
    s = Settings()
    assert s.max_turns == 40
