import pytest
from fastapi.testclient import TestClient

from api.main import app, sessions
from brain import availability


@pytest.fixture(autouse=True)
def clear_sessions():
    taken = set(availability.TAKEN_SLOTS)
    bookings = list(availability.BOOKINGS)
    sessions.clear()
    yield
    sessions.clear()
    availability.TAKEN_SLOTS.clear()
    availability.TAKEN_SLOTS.update(taken)
    availability.BOOKINGS[:] = bookings


client = TestClient(app)


def post_turn(session_id, text):
    return client.post("/turn", json={"session_id": session_id, "text": text})


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_turn_starts_session_and_asks():
    response = post_turn("api-start", "book a checkup")
    body = response.json()
    assert response.status_code == 200
    assert body["reply"]
    assert body["decision"]["state"] == "COLLECTING"


def test_turn_persists_session_across_calls():
    session_id = "api-persist"
    first = post_turn(session_id, "book a checkup on 2030-01-20 at 10am").json()
    second = post_turn(session_id, "Jordan Example").json()
    assert first["decision"]["slots"]["reason"] == "checkup"
    assert first["decision"]["slots"]["date"] == "2030-01-20"
    assert first["decision"]["slots"]["time"] == "10:00"
    assert second["decision"]["slots"]["patient_name"] == "Jordan Example"
    assert second["decision"]["slots"]["date"] == "2030-01-20"
    assert second["decision"]["slots"]["time"] == "10:00"
    assert second["decision"]["state"] == "COLLECTING"


def test_full_booking_over_http():
    session_id = "api-booking"
    post_turn(session_id, "book a checkup on 2030-01-20 at 10am")
    post_turn(session_id, "Jordan Example")
    post_turn(session_id, "5559876543")
    response = post_turn(session_id, "yes")
    body = response.json()
    assert response.status_code == 200
    assert body["decision"]["state"] == "BOOKED"
    assert "booked" in body["reply"].lower()


def test_reset_clears_session():
    session_id = "api-reset"
    post_turn(session_id, "book a checkup")
    reset = client.post("/reset", json={"session_id": session_id})
    fresh = post_turn(session_id, "book a checkup").json()
    assert reset.status_code == 200
    assert reset.json() == {"ok": True}
    assert fresh["decision"]["state"] == "COLLECTING"
    assert fresh["decision"]["pending_slot"] == "date"
