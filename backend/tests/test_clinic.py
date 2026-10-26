import pytest

from app import clinic
from app.config import get_settings


def test_doctors_for() -> None:
    assert len(clinic.doctors_for("general practice")) == 2


def test_doctor_by_id() -> None:
    nguyen = clinic.doctor_by_id("nguyen")
    assert nguyen is not None and nguyen.specialty == "dermatology"
    assert clinic.doctor_by_id("nope") is None


def test_cors_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "a,b")
    assert get_settings().cors_origins == ["a", "b"]
