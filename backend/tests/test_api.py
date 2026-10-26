from datetime import datetime

from fastapi.testclient import TestClient

from app.brain import Brain
from app.main import create_app
from app.scheduler import Schedule

client = TestClient(create_app(Brain(Schedule(), clock=lambda: datetime(2026, 10, 26, 10, 0))))


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_session_and_turn_flow():
    sid = client.post("/api/sessions").json()["session_id"]
    r = client.post(f"/api/sessions/{sid}/turn", json={"text": "I'd like to book a cleaning"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "book" and body["slots"]["service"] == "cleaning"
    assert body["trace"] and "day" in body["reply"].lower()


def test_unknown_session_is_404():
    assert client.post("/api/sessions/nope/turn", json={"text": "hi"}).status_code == 404


def test_too_long_input_is_rejected():
    sid = client.post("/api/sessions").json()["session_id"]
    assert client.post(f"/api/sessions/{sid}/turn", json={"text": "x" * 600}).status_code == 422
