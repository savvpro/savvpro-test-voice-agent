from pathlib import Path

import pytest

from backend.app import Settings


def test_neon_env_local_is_loaded_without_exposing_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    (tmp_path / ".env.local").write_text(
        "DATABASE_URL=postgresql://fake:fake@localhost/example\nNEON_BRANCH=production\n",
        encoding="utf-8",
    )
    assert Settings().database_url == "postgresql://fake:fake@localhost/example"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./environment.db")
    assert Settings().database_url == "sqlite:///./environment.db"


def test_zero_config_still_defaults_to_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings().database_url == "sqlite:///./workshop.db"
