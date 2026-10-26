"""HTTP integration tests with the real deterministic brain and temporary SQLite."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import sqlite3
from threading import Barrier

from fastapi.testclient import TestClient
import pytest

from app.main import create_app


REFERENCE = datetime(2026, 10, 26, 10)
DETAILS = {"date": "2026-10-27", "time": "19:00", "party_size": 4}
EMPTY = {"date": None, "time": None, "party_size": None}


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "api.sqlite3", reference_date=REFERENCE)
    with TestClient(app, raise_server_exceptions=False) as result:
        yield result


def store(client):
    return client.app.state.conversation_service.store


def start(client):
    response = client.post("/api/conversations/start")
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "ask_date"
    assert data["collected_data"] == EMPTY
    assert data["reservation"] is None
    return data["session_id"]


def send(client, sid, message, request_id="turn-1"):
    return client.post("/api/conversations/message", json={
        "session_id": sid, "message": message, "request_id": request_id,
    })


def ready(client, message="tomorrow at 7pm for 4"):
    sid = start(client)
    response = send(client, sid, message)
    assert response.status_code == 200
    assert response.json()["status"] == "confirm"
    assert response.json()["reservation"] is None
    return sid


def test_complete_reservation_is_saved_only_after_explicit_confirmation(client):
    sid = start(client)
    for index, (message, status) in enumerate([
        ("tomorrow", "ask_time"), ("7pm", "ask_party_size"), ("4", "confirm"),
    ]):
        response = send(client, sid, message, str(index))
        assert response.status_code == 200
        assert response.json()["session_id"] == sid
        assert response.json()["status"] == status
        assert response.json()["reservation"] is None
        assert store(client).list_reservations() == []

    response = send(client, sid, "yes", "confirm")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["collected_data"] == DETAILS
    saved = store(client).get_reservation(data["reservation"]["reservation_id"])
    assert saved is not None
    assert saved.party_size == 4
    assert saved.status == "confirmed"
    assert data["reservation"] == {
        "reservation_id": saved.reservation_id,
        "reservation_date": saved.reservation_date,
        "reservation_time": saved.reservation_time,
        "party_size": saved.party_size,
        "status": saved.status,
        "created_at": saved.created_at,
    }
    assert "request_id" not in data["reservation"]
    assert "table_id" not in data["reservation"]


@pytest.mark.parametrize("message", ["no", "not correct", "that's wrong", "incorrect", "no, correct"])
def test_rejected_confirmation_never_creates_reservation(client, message):
    sid = ready(client)
    data = send(client, sid, message, "reject").json()
    assert data["status"] == "confirm"
    assert "change" in data["message"]
    assert data["reservation"] is None
    assert store(client).list_reservations() == []


@pytest.mark.parametrize("message", ["yes", "correct", "book it", "sounds good"])
def test_valid_affirmations_create_exactly_one_booking(client, message):
    sid = ready(client)
    assert send(client, sid, message, "confirm").json()["status"] == "completed"
    assert len(store(client).list_reservations()) == 1


def test_affirmation_before_details_does_not_create_reservation(client):
    sid = start(client)
    for index, message in enumerate(["yes", "tomorrow", "yes", "7pm", "yes"]):
        assert send(client, sid, message, str(index)).status_code == 200
        assert store(client).list_reservations() == []


def test_affirmation_with_new_details_requires_another_confirmation(client):
    sid = ready(client)
    data = send(client, sid, "yes, for 6 people", "correction").json()
    assert data["status"] == "confirm"
    assert data["collected_data"]["party_size"] == 6
    assert store(client).list_reservations() == []
    assert send(client, sid, "yes", "confirm").json()["reservation"]["party_size"] == 6


@pytest.mark.parametrize("message,status,field,prompt", [
    ("February 30", "ask_date", "date", "valid"),
    ("April 31", "ask_date", "date", "valid"),
    ("2026-10-25", "ask_date", "date", "past"),
    ("tomorrow at 7:99pm for 4", "ask_time", "time", "valid"),
    ("tomorrow at 25:00 for 4", "ask_time", "time", "valid"),
    ("tomorrow at 13:75 for 4", "ask_time", "time", "valid"),
    ("tomorrow at 7pm for -2", "ask_party_size", "party_size", "at least 1"),
    ("tomorrow at 7pm for 0 guests", "ask_party_size", "party_size", "at least 1"),
    ("tomorrow at 7pm or 8pm for 4", "ask_time", "time", "choose one"),
])
def test_invalid_details_never_create_reservation(client, message, status, field, prompt):
    sid = start(client)
    response = send(client, sid, message)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == status
    assert data["collected_data"][field] is None
    assert prompt in data["message"].lower()
    assert send(client, sid, "yes", "premature").json()["status"] == status
    assert store(client).list_reservations() == []


def test_corrections_save_only_the_final_explicitly_accepted_details(client):
    sid = ready(client)
    data = send(client, sid, "no, make it 6 people", "correct-size").json()
    assert data["status"] == "confirm"
    assert data["collected_data"]["party_size"] == 6
    data = send(client, sid, "change the time to 8pm", "correct-time").json()
    assert data["status"] == "confirm"
    assert store(client).list_reservations() == []
    saved = send(client, sid, "yes", "accept").json()["reservation"]
    assert saved["reservation_time"] == "20:00"
    assert saved["party_size"] == 6


@pytest.mark.parametrize("message,field,status", [
    ("actually 50 people", "party_size", "ask_party_size"),
    ("actually February 30", "date", "ask_date"),
    ("change the time to 3am", "time", "ask_time"),
])
def test_invalid_correction_cannot_confirm_stale_data(client, message, field, status):
    sid = ready(client)
    data = send(client, sid, message, "invalid-correction").json()
    assert data["status"] == status
    assert data["collected_data"][field] is None
    assert send(client, sid, "yes", "premature").json()["status"] == status
    assert store(client).list_reservations() == []


def test_unavailable_slot_is_not_offered_for_confirmation_and_allows_new_time(client):
    store(client).create_reservation("2026-10-27", "19:00", 20, request_id="fake-occupied")
    sid = start(client)
    data = send(client, sid, "tomorrow at 7pm for 20").json()
    assert data["status"] == "ask_time"
    assert data["collected_data"] == {**DETAILS, "time": None, "party_size": 20}
    assert "no suitable table" in data["message"]
    assert data["reservation"] is None
    assert send(client, sid, "yes", "premature").json()["status"] == "ask_time"
    assert len(store(client).list_reservations()) == 1
    assert send(client, sid, "8:30pm", "new-time").json()["status"] == "confirm"
    data = send(client, sid, "book it", "confirm").json()
    assert data["status"] == "completed"
    assert data["reservation"]["reservation_time"] == "20:30"
    assert len(store(client).list_reservations()) == 2


def test_slot_taken_after_preflight_does_not_get_booked(client):
    sid = ready(client, "tomorrow at 7pm for 20")
    store(client).create_reservation("2026-10-27", "19:00", 20, request_id="fake-racing-booking")
    response = send(client, sid, "yes", "confirm")
    assert response.status_code == 200
    assert response.json()["status"] == "ask_time"
    assert response.json()["reservation"] is None
    assert "no suitable table" in response.json()["message"]
    assert len(store(client).list_reservations()) == 1


def test_booking_date_expiring_before_confirmation_requests_a_new_date(client, monkeypatch):
    sid = ready(client)
    monkeypatch.setattr(store(client), "_today", lambda: datetime(2026, 10, 28).date())
    response = send(client, sid, "yes", "confirm")
    assert response.status_code == 200
    assert response.json()["status"] == "ask_date"
    assert response.json()["collected_data"]["date"] is None
    assert response.json()["reservation"] is None
    assert store(client).list_reservations() == []


def test_cancel_and_restart_before_booking_never_save(client):
    sid = ready(client)
    assert send(client, sid, "cancel", "cancel").json()["status"] == "cancelled"
    assert send(client, sid, "yes", "after-cancel").json()["status"] == "cancelled"
    data = send(client, sid, "start over", "restart").json()
    assert data["status"] == "ask_date"
    assert data["collected_data"] == EMPTY
    assert store(client).list_reservations() == []
    assert send(client, sid, "tomorrow at 8pm for 2", "new-details").json()["status"] == "confirm"
    assert send(client, sid, "yes", "new-confirm").json()["status"] == "completed"
    assert len(store(client).list_reservations()) == 1


def test_completed_session_ignores_changes_and_restart_uses_a_new_booking_key(client):
    sid = ready(client)
    original = send(client, sid, "yes", "confirm").json()["reservation"]
    for index, text in enumerate(["change the time to 8pm", "cancel", "yes"]):
        data = send(client, sid, text, f"completed-{index}").json()
        assert data["status"] == "completed"
        assert data["reservation"] == original
        assert len(store(client).list_reservations()) == 1
    data = send(client, sid, "restart", "restart").json()
    assert data["reservation"] is None
    assert data["status"] == "ask_date"
    assert send(client, sid, "tomorrow at 8:30pm for 4", "new-details").json()["status"] == "confirm"
    second = send(client, sid, "yes", "new-confirm").json()["reservation"]
    assert second["reservation_id"] != original["reservation_id"]
    assert len(store(client).list_reservations()) == 2
    assert send(client, sid, "yes", "confirm").json()["reservation"] == original
    assert len(store(client).list_reservations()) == 2


def test_repeated_message_id_replays_without_advancing_state(client):
    sid = start(client)
    first = send(client, sid, "tomorrow")
    assert send(client, sid, "tomorrow").json() == first.json()
    assert len(client.app.state.conversation_service.engine.get_session(sid).history) == 2
    conflict = send(client, sid, "Friday")
    assert conflict.status_code == 409
    session = client.app.state.conversation_service.engine.get_session(sid)
    assert session.state.value == "ask_time"
    assert session.time is None
    assert store(client).list_reservations() == []


def test_duplicate_confirmation_ids_and_new_confirmation_ids_never_duplicate_bookings(client):
    sid = ready(client)
    first = send(client, sid, "yes", "confirm").json()
    assert send(client, sid, "yes", "confirm").json() == first
    assert send(client, sid, "yes", "another-id").json()["reservation"] == first["reservation"]
    assert len(store(client).list_reservations()) == 1


@pytest.mark.parametrize("body", [
    {}, {"session_id": "s", "message": "hello"},
    {"session_id": "s", "message": "", "request_id": "r"},
    {"session_id": "s", "message": "  ", "request_id": "r"},
    {"session_id": "s", "message": 123, "request_id": "r"},
    {"session_id": "s", "message": "x" * 2001, "request_id": "r"},
    {"session_id": None, "message": "hello", "request_id": "r"},
    {"session_id": "s", "message": "hello", "request_id": " "},
    {"session_id": "s", "message": "hello", "request_id": "r", "status": "completed"},
])
def test_invalid_request_payloads_return_422_without_writes(client, body):
    assert client.post("/api/conversations/message", json=body).status_code == 422
    assert store(client).list_reservations() == []


def test_malformed_json_unknown_session_and_unrelated_input(client):
    assert client.post("/api/conversations/message", content="{", headers={"Content-Type": "application/json"}).status_code == 422
    assert send(client, "nonexistent", "hello").status_code == 404
    sid = start(client)
    response = send(client, sid, "what is the weather like")
    assert response.status_code == 200
    assert response.json()["status"] == "ask_date"
    assert store(client).list_reservations() == []


def test_database_preflight_failure_is_sanitized_and_turn_can_be_retried(client, monkeypatch):
    sid = start(client)
    service = client.app.state.conversation_service

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("SECRET database /private/internal.sqlite3 password=hidden")

    with monkeypatch.context() as context:
        context.setattr(store(client), "check_availability", fail)
        response = send(client, sid, "tomorrow at 7pm for 4")
    assert response.status_code == 503
    assert "SECRET" not in response.text
    assert "/private" not in response.text
    assert "hidden" not in response.text
    assert "retry" in response.json()["detail"].lower()
    session = service.engine.get_session(sid)
    assert session.state.value == "ask_date"
    assert session.collected_data() == EMPTY
    assert len(session.history) == 1
    assert send(client, sid, "tomorrow at 7pm for 4").json()["status"] == "confirm"
    assert store(client).list_reservations() == []


@pytest.mark.parametrize("error_type", [sqlite3.OperationalError, sqlite3.IntegrityError, OSError])
def test_creation_error_never_returns_completed_and_can_retry(client, monkeypatch, error_type):
    sid = ready(client)

    def fail(*args, **kwargs):
        raise error_type("SECRET internal storage error")

    with monkeypatch.context() as context:
        context.setattr(store(client), "create_reservation", fail)
        response = send(client, sid, "yes", "confirm")
    assert response.status_code == 503
    assert "SECRET" not in response.text
    session = client.app.state.conversation_service.engine.get_session(sid)
    assert session.state.value == "confirm"
    assert session.collected_data() == DETAILS
    assert store(client).list_reservations() == []
    assert send(client, sid, "yes", "confirm").json()["status"] == "completed"
    assert len(store(client).list_reservations()) == 1


def test_uncertain_commit_result_can_be_retried_without_a_duplicate(client, monkeypatch):
    sid = ready(client, "tomorrow at 7pm for 20")
    actual_create = store(client).create_reservation

    def commit_then_fail(*args, **kwargs):
        actual_create(*args, **kwargs)
        raise sqlite3.OperationalError("SECRET error after commit")

    with monkeypatch.context() as context:
        context.setattr(store(client), "create_reservation", commit_then_fail)
        response = send(client, sid, "yes", "confirm")
    assert response.status_code == 503
    assert "SECRET" not in response.text
    original = store(client).list_reservations()
    assert len(original) == 1
    data = send(client, sid, "yes", "confirm").json()
    assert data["status"] == "completed"
    assert data["reservation"]["reservation_id"] == original[0].reservation_id
    assert store(client).list_reservations() == original


def test_unexpected_service_error_is_sanitized_and_state_restored(client, monkeypatch):
    sid = start(client)

    def fail(*args, **kwargs):
        raise RuntimeError("SECRET unexpected failure")

    with monkeypatch.context() as context:
        context.setattr(store(client), "check_availability", fail)
        response = send(client, sid, "tomorrow at 7pm for 4")
    assert response.status_code == 500
    assert "SECRET" not in response.text
    assert client.app.state.conversation_service.engine.get_session(sid).state.value == "ask_date"
    assert store(client).list_reservations() == []


def test_initialization_failure_keeps_errors_private(tmp_path, monkeypatch):
    app = create_app(tmp_path / "missing" / "api.sqlite3", reference_date=REFERENCE)

    def fail():
        raise OSError("SECRET initialization path")

    monkeypatch.setattr(app.state.conversation_service.store, "initialize_database", fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        sid = start(client)
        response = send(client, sid, "tomorrow at 7pm for 4")
        assert response.status_code == 503
        assert "SECRET" not in response.text


def test_independent_sessions_do_not_share_collected_data(client):
    first, second = start(client), start(client)
    assert first != second
    assert send(client, first, "tomorrow").json()["status"] == "ask_time"
    data = send(client, second, "Friday at 8pm for 2").json()
    assert data["status"] == "confirm"
    first_session = client.app.state.conversation_service.engine.get_session(first)
    assert first_session.time is None
    assert first_session.party_size is None


def test_concurrent_confirmation_retries_return_one_booking(client):
    sid = ready(client)
    barrier = Barrier(2)

    def confirm(_):
        barrier.wait(timeout=10)
        return send(client, sid, "yes", "same-confirm")

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(confirm, range(2)))
    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json() == responses[1].json()
    assert len(store(client).list_reservations()) == 1


def test_two_ready_sessions_cannot_confirm_the_same_last_table(client):
    first = ready(client, "tomorrow at 7pm for 20")
    second = ready(client, "tomorrow at 7pm for 20")
    barrier = Barrier(2)

    def confirm(sid):
        barrier.wait(timeout=10)
        return send(client, sid, "yes", "confirm")

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(confirm, [first, second]))
    assert all(response.status_code == 200 for response in responses)
    assert sorted(response.json()["status"] for response in responses) == ["ask_time", "completed"]
    assert len(store(client).list_reservations()) == 1


def test_sessions_are_not_recovered_after_process_restart_but_bookings_persist(client):
    sid = ready(client)
    saved = send(client, sid, "yes", "confirm").json()["reservation"]
    app = create_app(store(client).database_path, reference_date=REFERENCE)
    with TestClient(app) as restarted:
        assert send(restarted, sid, "yes", "confirm").status_code == 404
        assert store(restarted).get_reservation(saved["reservation_id"]) is not None
        assert len(store(restarted).list_reservations()) == 1
