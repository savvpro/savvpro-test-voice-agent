"""End-to-end tests for the FastAPI app via httpx/TestClient."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "version" in body
    assert "bookings_count" in body


def test_reset_creates_new_session(client):
    r = client.post("/api/reset", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "greeting"
    assert "session_id" in body
    assert "Copper Spoon" in body["last_prompt"]


def test_full_booking_via_api(client):
    # Start fresh
    r = client.post("/api/reset", json={})
    sid = r.json()["session_id"]

    # Greet
    r = client.post("/api/chat", json={"session_id": sid, "text": "hi"})
    assert r.status_code == 200
    assert r.json()["state"] == "ask_date"

    # Book
    r = client.post("/api/chat", json={"session_id": sid, "text": "friday at 8pm for 4 people"})
    assert r.json()["state"] == "ask_name"

    # Name
    r = client.post("/api/chat", json={"session_id": sid, "text": "John Smith"})
    assert r.json()["state"] == "ask_phone"

    # Phone
    r = client.post("/api/chat", json={"session_id": sid, "text": "555-123-4567"})
    assert r.json()["state"] == "confirm"

    # Confirm
    r = client.post("/api/chat", json={"session_id": sid, "text": "yes"})
    body = r.json()
    assert body["state"] == "booked"
    assert body["booking_id"] is not None
    assert "John Smith" in body["text"]

    # History should record everything
    r = client.get(f"/api/sessions/{sid}")
    assert r.status_code == 200
    history = r.json()["history"]
    assert len(history) >= 10  # 5 caller + 5 assistant turns


def test_session_persistence(client):
    """Two requests with the same session_id should share state."""
    r = client.post("/api/reset", json={})
    sid = r.json()["session_id"]

    client.post("/api/chat", json={"session_id": sid, "text": "hi"})
    r = client.post("/api/chat", json={"session_id": sid, "text": "tomorrow"})
    assert r.json()["state"] == "ask_time"

    # Next request — same session_id — should remember we're asking time
    r = client.post("/api/chat", json={"session_id": sid, "text": "7pm"})
    assert r.json()["state"] == "ask_party_size"


def test_end_call_on_goodbye(client):
    r = client.post("/api/reset", json={})
    sid = r.json()["session_id"]
    client.post("/api/chat", json={"session_id": sid, "text": "hi"})
    r = client.post("/api/chat", json={"session_id": sid, "text": "bye"})
    assert r.json()["end_call"] is True


def test_404_for_unknown_session(client):
    r = client.get("/api/sessions/does-not-exist")
    assert r.status_code == 404


def test_empty_input_doesnt_crash(client):
    r = client.post("/api/reset", json={})
    sid = r.json()["session_id"]
    r = client.post("/api/chat", json={"session_id": sid, "text": ""})
    assert r.status_code == 200
    assert "didn't hear" in r.json()["text"].lower() or "still there" in r.json()["text"].lower()
