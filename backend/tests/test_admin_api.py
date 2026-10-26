"""HTTP-level admin + health + rate-limit + persistence checks."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.engine import availability
from app.engine.dialogue import DialogueEngine
from app.main import app
from app.rate_limit import turn_limiter


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["persistence"] == "sqlite"
    assert body["db_ok"] is True
    assert body["ok"] is True
    assert "booking_count" in body
    assert "X-Request-Id" in r.headers
    assert "X-Response-Time-Ms" in r.headers


def test_admin_requires_password(client):
    r = client.get("/api/admin/bookings")
    assert r.status_code == 401


def test_admin_wrong_password(client):
    r = client.get(
        "/api/admin/bookings", headers={"X-Admin-Password": "nope"}
    )
    assert r.status_code == 401


def test_admin_list_cancel_restore_search(client):
    rec = availability.store.book("2026-11-01", "18:00", 4, guest_name="Alex")
    assert rec is not None
    headers = {"X-Admin-Password": "admin"}

    r = client.get("/api/admin/bookings", headers=headers)
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()["bookings"]]
    assert rec.id in ids

    r = client.get(
        "/api/admin/bookings",
        params={"q": rec.id[-4:]},
        headers=headers,
    )
    assert r.status_code == 200
    assert any(b["id"] == rec.id for b in r.json()["bookings"])

    r = client.get(
        "/api/admin/open-slots",
        params={"date": "2026-11-01", "party_size": 4},
        headers=headers,
    )
    assert r.status_code == 200

    r = client.delete(f"/api/admin/bookings/{rec.id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    r = client.get(
        "/api/admin/bookings",
        params={"include_cancelled": False},
        headers=headers,
    )
    assert rec.id not in [b["id"] for b in r.json()["bookings"]]

    r = client.post(
        f"/api/admin/bookings/{rec.id}/restore", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    got = availability.store.get_booking(rec.id)
    assert got is not None
    assert got.status == "active"


def test_admin_csv_and_stats_and_seed(client):
    headers = {"X-Admin-Password": "admin"}
    r = client.post("/api/admin/seed", headers=headers)
    assert r.status_code == 200
    assert r.json()["created"] >= 1

    r = client.get("/api/admin/stats", headers=headers)
    assert r.status_code == 200
    stats = r.json()
    assert stats["total_active"] >= 1
    assert "today_seats" in stats

    r = client.get("/api/admin/bookings.csv", headers=headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert "id,restaurant,date" in r.text
    assert "HLB-" in r.text


def test_rate_limit_blocks_when_enabled(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    turn_limiter.reset()
    turn_limiter.limit = 3
    turn_limiter.window = 60.0

    sid = "rate-test"
    client.post("/api/reset", json={"session_id": sid})
    for _ in range(3):
        r = client.post("/api/turn", json={"session_id": sid, "text": "hi"})
        assert r.status_code == 200
    r = client.post("/api/turn", json={"session_id": sid, "text": "hi"})
    assert r.status_code == 429
    turn_limiter.reset()


def test_persistence_across_engine_instances():
    """Two DialogueEngine instances share the same SQLite store."""
    e1 = DialogueEngine()
    sid = "persist-engines"
    e1.reset(sid)
    r = e1.handle_turn(sid, "tomorrow at 7 for 2")
    assert r.state == "confirm"
    r = e1.handle_turn(sid, "yes")
    assert r.booking is not None
    booking_id = r.booking.id
    assert r.confirmation is not None
    assert r.confirmation.code == booking_id

    e2 = DialogueEngine()
    listed = availability.store.list_bookings()
    assert any(b.id == booking_id for b in listed)

    # Rebind / new store on same path still sees it
    path = availability.active_db_path()
    availability.rebind_store(path)
    got = availability.store.get_booking(booking_id)
    assert got is not None
    assert got.party_size == 2
