from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

NOW = datetime(2026, 10, 26, 9, tzinfo=ZoneInfo("Asia/Karachi"))


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings, lambda: NOW)) as client:
        yield client


def new_session(client):
    response = client.post("/api/sessions")
    assert response.status_code == 201, response.text
    return response.json()


def turn(client, context, text, request_id=None):
    response = client.post(f"/api/sessions/{context['id']}/turns", json={
        "text": text, "request_id": request_id or uuid4().hex,
        "expected_revision": context["revision"],
    })
    assert response.status_code == 200, response.text
    return response.json()


def proposal(client, text="Book a haircut tomorrow at 3 PM"):
    c = turn(client, new_session(client), text)
    c = turn(client, c, "Alex Example")
    assert c["state"] == "AWAITING_CONFIRMATION", c
    return c


def book(client, text="Book a haircut tomorrow at 3 PM"):
    c = turn(client, proposal(client, text), "yes")
    assert c["state"] == "BOOKING_COMPLETE", c
    return c
