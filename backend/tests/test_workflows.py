from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import Appointment
from app.bookings import Bookings
from app.brain.engine import BookingError
from app.main import create_app
from app.schemas import Entities
from conftest import NOW, book, new_session, proposal, turn


def count(client):
    with Session(client.app.state.database.engine) as db:
        return db.scalar(select(func.count()).select_from(Appointment))


def test_create_requires_explicit_confirmation_and_persists(client, settings):
    c = proposal(client)
    assert count(client) == 0
    c = turn(client, c, "maybe")
    assert count(client) == 0
    c = turn(client, c, "yes")
    assert count(client) == 1
    reference = c["appointment"]["reference"]
    assert c["appointment"]["starts_at"] == "2026-10-27T15:00:00+05:00"
    assert c["appointment"]["ends_at"] == "2026-10-27T15:30:00+05:00"
    with TestClient(create_app(settings, lambda: NOW)) as restarted:
        assert restarted.get(f"/api/appointments/{reference}").json() == c["appointment"]
        assert restarted.get(f"/api/sessions/{c['id']}").json() == c


def test_correction_rechecks_and_changes_actual_booking(client):
    book(client)
    c = turn(client, new_session(client), "book a haircut tomorrow at 4 PM")
    c = turn(client, c, "Alex Example")
    c = turn(client, c, "Actually make it 3 PM")
    assert c["entities"]["time"] is None
    assert c["proposed_action"] is None
    assert "taken" in c["reply"]
    c = turn(client, c, "5 PM")
    assert c["entities"]["name"] == "Alex Example"
    c = turn(client, c, "yes")
    assert "T17:00:00" in c["appointment"]["starts_at"]


def test_availability_uses_duration_and_persisted_bookings(client):
    book(client)
    result = client.get("/api/availability", params={"service": "combo", "day": "2026-10-27"})
    assert result.status_code == 200
    slots = result.json()["slots"]
    assert "14:10" in slots  # ends at 15:00; half-open intervals can touch
    assert "14:20" not in slots
    assert "15:00" not in slots
    assert "15:30" in slots
    assert "18:10" in slots
    assert "18:20" not in slots
    c = turn(client, new_session(client), "check availability for a haircut Friday afternoon")
    assert c["state"] == "COMPLETED"
    assert all("12:00" <= s < "17:00" for s in c["available_slots"])
    assert count(client) == 1


def test_reschedule_and_cancel_require_confirmation(client):
    original = book(client)["appointment"]
    reference = original["reference"]
    c = turn(client, new_session(client), f"reschedule {reference}")
    assert c["missing_information"] == ["date", "time"]
    c = turn(client, c, "Friday at 5 PM")
    assert c["proposed_action"] == "reschedule"
    assert client.get(f"/api/appointments/{reference}").json() == original
    c = turn(client, c, "yes")
    assert c["appointment"]["starts_at"] == "2026-10-30T17:00:00+05:00"
    assert c["appointment"]["version"] == 2
    c = turn(client, new_session(client), f"cancel my booking {reference}")
    assert c["proposed_action"] == "cancel"
    assert client.get(f"/api/appointments/{reference}").json()["status"] == "confirmed"
    c = turn(client, c, "no")
    assert client.get(f"/api/appointments/{reference}").json()["status"] == "confirmed"
    c = turn(client, c, f"cancel {reference}")
    c = turn(client, c, "confirm")
    assert c["appointment"]["status"] == "cancelled"
    assert "17:00" in client.get("/api/availability", params={"service": "haircut", "day": "2026-10-30"}).json()["slots"]


def test_reschedule_conflict_preserves_original(client):
    original = book(client)["appointment"]
    book(client, "book a haircut Friday at 5 PM")
    c = turn(client, new_session(client), f"reschedule {original['reference']} Friday at 5 PM")
    assert c["last_decision"]["matched_rule"] == "availability.rejected"
    c = turn(client, c, "yes")
    assert c["last_decision"]["matched_rule"] == "confirmation.no_proposal"
    assert client.get(f"/api/appointments/{original['reference']}").json() == original


def test_commit_rechecks_availability_after_other_session_takes_slot(client):
    a, b = proposal(client), proposal(client)
    a = turn(client, a, "yes")
    b = turn(client, b, "yes")
    assert b["appointment"] is None
    assert b["last_decision"]["matched_rule"] == "commit.rejected"
    assert count(client) == 1


def test_parallel_confirmations_serialize_across_app_instances(client, settings):
    a, b = proposal(client), proposal(client)
    # A second engine/connection pool stands in for an independent server worker.
    with TestClient(create_app(settings, lambda: NOW)) as other:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(turn, client, a, "yes"), executor.submit(turn, other, b, "yes")]
            results = [f.result() for f in futures]
    assert sum(r["state"] == "BOOKING_COMPLETE" for r in results) == 1
    assert count(client) == 1


def test_duplicate_request_replays_receipt_not_side_effect(client):
    c = proposal(client)
    first = turn(client, c, "yes", "duplicate-confirm-001")
    replay = turn(client, c, "yes", "duplicate-confirm-001")
    assert replay == first
    assert count(client) == 1
    response = client.post(f"/api/sessions/{c['id']}/turns", json={
        "text": "no", "request_id": "duplicate-confirm-001", "expected_revision": c["revision"],
    })
    assert response.status_code == 409


def test_parallel_duplicate_requests_have_one_effect(client):
    c = proposal(client)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(turn, client, c, "yes", "same-request-001") for _ in range(2)]
        results = [f.result() for f in futures]
    assert results[0] == results[1]
    assert count(client) == 1


def test_stale_session_revision_rejected(client):
    c = new_session(client)
    turn(client, c, "book a haircut")
    response = client.post(f"/api/sessions/{c['id']}/turns", json={
        "text": "cancel", "request_id": uuid4().hex, "expected_revision": 0,
    })
    assert response.status_code == 409


def test_stale_booking_version_requires_new_review(client):
    original = book(client)["appointment"]
    a = turn(client, new_session(client), f"cancel {original['reference']}")
    b = turn(client, new_session(client), f"reschedule {original['reference']} Friday at 4 PM")
    b = turn(client, b, "yes")
    a = turn(client, a, "yes")
    assert a["last_decision"]["matched_rule"] == "commit.rejected"
    assert a["missing_information"] == ["reference"]
    assert client.get(f"/api/appointments/{original['reference']}").json()["status"] == "confirmed"


@pytest.mark.parametrize("text,field", [
    ("book a haircut yesterday", "date"),
    ("book a haircut 2026-10-25 at 3 PM", "date"),
    ("book a haircut Sunday at 3 PM", "date"),
    ("book a haircut tomorrow at 9 AM", "time"),
    ("book a haircut tomorrow at 7 PM", "time"),
    ("book haircut and beard tomorrow at 6:20 PM", "time"),
    ("book a haircut 2027-10-26 at 3 PM", "date"),
])
def test_invalid_business_dates_and_boundaries(client, text, field):
    c = turn(client, new_session(client), text)
    assert field in c["missing_information"]
    assert c["proposed_action"] is None
    assert count(client) == 0


@pytest.mark.parametrize("text", ["book a haircut tomorrow at 10 AM", "book a haircut tomorrow at 6:30 PM", "book haircut and beard tomorrow at 6:10 PM"])
def test_exact_open_and_close_boundaries_allowed(client, text):
    c = book(client, text)
    assert c["appointment"]["status"] == "confirmed"


def test_sessions_are_isolated_and_unknown_input_safe(client):
    a, b = new_session(client), new_session(client)
    a = turn(client, a, "book a haircut tomorrow at 5 PM")
    b = turn(client, b, "yes")
    assert b["entities"]["service"] is None
    assert b["last_decision"]["matched_rule"] == "confirmation.no_proposal"
    b = turn(client, b, "launch a rocket")
    assert b["last_decision"]["intent"] == "UNKNOWN"
    assert count(client) == 0


@pytest.mark.parametrize("payload", [
    {"text": "", "request_id": "valid-id-001", "expected_revision": 0},
    {"text": "   ", "request_id": "valid-id-001", "expected_revision": 0},
    {"text": "x" * 1001, "request_id": "valid-id-001", "expected_revision": 0},
    {"text": "hello", "request_id": "bad", "expected_revision": 0},
    {"text": "hello", "request_id": "valid-id-001", "expected_revision": -1},
    {"text": "hello", "request_id": "valid-id-001"},
    {"text": "hello", "request_id": "valid-id-001", "expected_revision": 0, "confirm": True},
])
def test_invalid_input(client, payload):
    c = new_session(client)
    assert client.post(f"/api/sessions/{c['id']}/turns", json=payload).status_code == 422


def test_missing_resources_and_availability_validation(client):
    assert client.get("/api/sessions/missing").status_code == 404
    assert client.get("/api/appointments/NL-00000000").status_code == 404
    assert client.get("/api/availability", params={"service": "massage", "day": "2026-10-27"}).status_code == 422
    assert client.get("/api/availability", params={"service": "haircut", "day": "not-a-date"}).status_code == 422
    c = turn(client, new_session(client), "cancel NL-00000000")
    assert c["missing_information"] == ["reference"]


def test_database_failure_rolls_back_booking_state_and_receipt(client):
    c = proposal(client)
    with patch.object(Session, "commit", side_effect=OperationalError("simulated", {}, Exception("disk full"))):
        response = client.post(f"/api/sessions/{c['id']}/turns", json={
            "text": "yes", "request_id": "failure-confirm-001", "expected_revision": c["revision"],
        })
    assert response.status_code == 503
    assert count(client) == 0
    assert client.get(f"/api/sessions/{c['id']}").json() == c
    recovered = turn(client, c, "yes", "failure-confirm-001")
    assert recovered["state"] == "BOOKING_COMPLETE"
    assert count(client) == 1


def test_availability_to_booking_retains_query_details(client):
    c = turn(client, new_session(client), "check haircut availability Friday afternoon")
    assert c["available_slots"]
    c = turn(client, c, "book at 3 PM")
    assert c["entities"]["date"] == "2026-10-30"
    assert c["entities"]["service"] == "haircut"
    assert c["missing_information"] == ["name"]
    c = turn(client, c, "Alex Example")
    c = turn(client, c, "yes")
    assert c["appointment"]["starts_at"] == "2026-10-30T15:00:00+05:00"


def test_no_availability_recovers_with_another_date(client):
    book(client)
    c = turn(client, new_session(client), "check haircut availability tomorrow at 3 PM")
    assert c["available_slots"] == []
    assert c["missing_information"] == ["date"]
    c = turn(client, c, "Friday")
    assert c["available_slots"] == ["15:00"]


def test_business_clock_uses_configured_zone_and_utc_storage(settings):
    # UTC Monday night is already Tuesday in Karachi.
    now = datetime(2026, 10, 26, 23, 45, tzinfo=timezone.utc)
    with TestClient(create_app(settings, lambda: now)) as client:
        c = book(client)
        assert c["entities"]["date"] == "2026-10-28"
        with Session(client.app.state.database.engine) as db:
            appointment = db.get(Appointment, c["appointment"]["reference"])
            stored = datetime.fromtimestamp(appointment.starts_at, timezone.utc)
        assert stored == datetime(2026, 10, 28, 10, tzinfo=timezone.utc)


def test_ending_while_identifying_a_booking_does_not_claim_a_commit(client):
    reference = book(client)["appointment"]["reference"]
    c = turn(client, new_session(client), f"cancel {reference}")
    c = turn(client, c, "goodbye")
    assert c["last_committed_action"] is None
    assert c["proposed_action"] is None
    assert client.get(f"/api/appointments/{reference}").json()["status"] == "confirmed"


def test_caught_domain_error_cannot_partially_reschedule(client, settings):
    original = book(client)["appointment"]
    with client.app.state.database.transaction() as db:
        service = Bookings(db, settings, NOW)
        invalid = Entities(reference=original["reference"], service="beard", name="",
                           date="2026-10-30", time="16:00")
        # The state machine catches domain errors and commits its clarification;
        # the booking object must remain untouched even when the error is caught.
        with pytest.raises(BookingError):
            service.reschedule(invalid, original["version"])
    assert client.get(f"/api/appointments/{original['reference']}").json() == original
