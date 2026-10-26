from fastapi.testclient import TestClient

from app.api.store import CallStore
from app.main import create_app
from tests.conftest import NOW


def client():
    return TestClient(create_app(CallStore(clock=lambda: NOW)))


def test_full_call_over_http():
    c = client()
    r = c.post("/api/calls")
    assert r.status_code == 201
    call_id = r.json()["call_id"]
    assert "Brightside" in r.json()["reply"]

    for line in ["book a cleaning tomorrow at 10 am", "Jane Doe", "555 123 4567"]:
        r = c.post(f"/api/calls/{call_id}/turns", json={"text": line})
        assert r.status_code == 200
    assert r.json()["action"] == "confirm"
    r = c.post(f"/api/calls/{call_id}/turns", json={"text": "yes"})
    assert r.json()["action"] == "booked" and r.json()["ended"]

    history = c.get(f"/api/calls/{call_id}").json()
    assert len(history["turns"]) == 4

    schedule = c.get("/api/schedule").json()["bookings"]
    jane = next(b for b in schedule if b["name"] == "Jane Doe")
    assert jane["phone"] == "ends in 4567"  # phone numbers are masked


def test_unknown_call_is_404():
    c = client()
    assert c.post("/api/calls/nope/turns", json={"text": "hi"}).status_code == 404
    assert c.get("/api/calls/nope").status_code == 404


def test_text_too_long_is_rejected():
    c = client()
    call_id = c.post("/api/calls").json()["call_id"]
    assert c.post(f"/api/calls/{call_id}/turns", json={"text": "a" * 501}).status_code == 422


def test_reset_restores_demo_booking():
    c = client()
    call_id = c.post("/api/calls").json()["call_id"]
    for line in ["cancel my appointment", "5550142233", "yes"]:
        c.post(f"/api/calls/{call_id}/turns", json={"text": line})
    assert c.get("/api/schedule").json()["bookings"] == []
    c.post("/api/reset")
    assert len(c.get("/api/schedule").json()["bookings"]) == 1


def test_health():
    assert client().get("/api/health").json() == {"status": "ok"}
