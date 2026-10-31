from conftest import MONDAY_8AM
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.sessions import SessionStore


def client() -> TestClient:
    return TestClient(create_app(clock=lambda: MONDAY_8AM))


def test_health():
    assert client().get("/health").json() == {"status": "ok"}


def test_full_turn_roundtrip_exposes_decision_trace():
    c = client()
    start = c.post("/api/sessions")
    assert start.status_code == 201
    sid = start.json()["session_id"]
    assert "Green Valley Clinic" in start.json()["reply"]

    body = c.post(f"/api/sessions/{sid}/turn", json={"text": "I want to book a dental appointment"}).json()
    assert body["intent"] == "book"
    assert body["slots"]["specialty"] == "dental"
    assert body["state"] == "collecting"
    assert body["trace"]["entities"]["specialty"] == "dental"
    assert body["trace"]["rule"]
    assert body["ended"] is False


def test_unknown_session_is_404():
    assert client().post("/api/sessions/nope/turn", json={"text": "hi"}).status_code == 404


def test_validation_rejects_oversized_text_and_bad_confidence():
    c = client()
    sid = c.post("/api/sessions").json()["session_id"]
    assert c.post(f"/api/sessions/{sid}/turn", json={"text": "x" * 501}).status_code == 422
    assert c.post(f"/api/sessions/{sid}/turn", json={"text": "hi", "confidence": 3}).status_code == 422


def test_delete_session():
    c = client()
    sid = c.post("/api/sessions").json()["session_id"]
    assert c.delete(f"/api/sessions/{sid}").status_code == 204
    assert c.post(f"/api/sessions/{sid}/turn", json={"text": "hi"}).status_code == 404


def test_session_store_expires_idle_sessions():
    now = [0.0]
    store = SessionStore(ttl_seconds=10, timer=lambda: now[0])
    session = store.create()
    now[0] = 5
    assert store.get(session.id) is session  # touching keeps it alive
    now[0] = 14
    assert store.get(session.id) is session
    now[0] = 30
    assert store.get(session.id) is None
