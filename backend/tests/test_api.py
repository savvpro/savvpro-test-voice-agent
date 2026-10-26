from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

NOW = datetime(2026, 10, 26, 10, 0)


@pytest.fixture
def client():
    app = create_app(Settings(allowed_origins=["http://localhost:3000"], seed_demo_data=True), clock=lambda: NOW)
    return TestClient(app)


def turn(client, session_id, text):
    response = client.post(f"/api/sessions/{session_id}/turns", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_start_session_returns_a_greeting(client):
    response = client.post("/api/sessions")
    assert response.status_code == 201
    body = response.json()
    assert "Smile Dental Clinic" in body["reply"] and body["state"] == "ask_service" and not body["done"]


def test_full_call_over_http(client):
    session_id = client.post("/api/sessions").json()["session_id"]
    body = turn(client, session_id, "I need a cleaning on friday at 2 pm")
    assert body["state"] == "ask_patient" and body["slots"]["time"] == "14:00"
    assert "book" in body["intents"] or body["trace"]
    turn(client, session_id, "Sara Khan")
    turn(client, session_id, "03123456789")
    body = turn(client, session_id, "yes")
    assert body["done"] and "booked" in body["actions"]
    assert client.get(f"/api/sessions/{session_id}").json()["done"] is True


def test_seeded_slot_is_really_taken(client):
    session_id = client.post("/api/sessions").json()["session_id"]
    body = turn(client, session_id, "a checkup tomorrow at 9 am")
    assert "slot_taken" in body["actions"] and body["state"] == "offer_alternative"


def test_two_callers_cannot_book_the_same_slot(client):
    first = client.post("/api/sessions").json()["session_id"]
    second = client.post("/api/sessions").json()["session_id"]
    for session_id in (first, second):
        turn(client, session_id, "cleaning on friday at 3 pm")
        turn(client, session_id, "Ali")
        turn(client, session_id, "03123456789")
    assert turn(client, first, "yes")["done"]
    body = turn(client, second, "yes")
    assert "slot_taken" in body["actions"] and not body["done"]


def test_unknown_session_is_404(client):
    assert client.post("/api/sessions/nope/turns", json={"text": "hi"}).status_code == 404
    assert client.get("/api/sessions/nope").status_code == 404


@pytest.mark.parametrize("payload", [{}, {"text": ""}, {"text": "x" * 501}])
def test_bad_input_is_rejected(client, payload):
    session_id = client.post("/api/sessions").json()["session_id"]
    assert client.post(f"/api/sessions/{session_id}/turns", json=payload).status_code == 422


def test_whitespace_only_text_is_rejected(client):
    session_id = client.post("/api/sessions").json()["session_id"]
    assert client.post(f"/api/sessions/{session_id}/turns", json={"text": "   "}).status_code == 422


def test_cors_allows_only_the_configured_origin(client):
    ok = client.options(
        "/api/sessions",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.options(
        "/api/sessions",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in bad.headers
