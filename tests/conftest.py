import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app import create_app
from backend.database import make_engine
from backend.domain import PKT

NOW = datetime(2026, 10, 26, 10, 0, tzinfo=PKT)
load_dotenv(".env.test")


@pytest.fixture(params=["sqlite", "postgres"])
def client(request: Any, tmp_path: Path) -> Iterator[TestClient]:
    if request.param == "postgres":
        url = os.getenv("TEST_DATABASE_URL")
        if not url:
            pytest.skip("Set TEST_DATABASE_URL to verify Postgres parity")
        base_engine = make_engine(url)
        schema = "test_" + uuid4().hex
        with base_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = base_engine.execution_options(schema_translate_map={None: schema})
    else:
        base_engine = make_engine("sqlite:///" + (tmp_path / "test.db").as_posix())
        engine = base_engine
    app = create_app(database_engine=engine, now=lambda: NOW)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if request.param == "postgres":
            with base_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        base_engine.dispose()


def start(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/session")
    assert response.status_code == 200, response.text
    return response.json()


def turn(
    client: TestClient, text: str, revision: int | None = None, turn_id: str | None = None
) -> dict[str, Any]:
    if revision is None:
        revision = start(client)["revision"]
    response = client.post(
        "/api/turn", json={"text": text, "turn_id": turn_id or uuid4().hex, "revision": revision}
    )
    assert response.status_code == 200, response.text
    return response.json()
