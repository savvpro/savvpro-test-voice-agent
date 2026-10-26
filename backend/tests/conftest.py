"""Shared fixtures and workspace-local temporary storage for repeatable runs."""

import shutil
import uuid
from pathlib import Path

import pytest
from app import main
from app.store import Store
from fastapi.testclient import TestClient

TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"


def pytest_configure(config):
    if not config.option.basetemp:
        TEST_ROOT.mkdir(exist_ok=True)
        config.option.basetemp = str(TEST_ROOT / ("run-" + uuid.uuid4().hex))


def pytest_sessionfinish(session, exitstatus):
    target = Path(session.config.option.basetemp).resolve()
    # Delete only the exact unique child created for this run, never user paths.
    if (
        target.parent == TEST_ROOT.resolve()
        and target.name.startswith("run-")
        and target.exists()
    ):
        shutil.rmtree(target)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", Store(str(tmp_path / "test.db")))
    return TestClient(main.app)
