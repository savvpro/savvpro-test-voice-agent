from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from lost_property.config import Settings
from lost_property.main import create_app
from lost_property.persistence.database import Database
from lost_property.persistence.fixtures import demo_items
from lost_property.persistence.models import CaseRow

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        allowed_origins=("http://testserver",),
    )
    db = Database(settings.database_url)
    db.migrate()
    db.seed(demo_items(NOW.date()))
    db.engine.dispose()
    application = create_app(settings, clock=lambda: NOW)
    with TestClient(application, headers=ORIGIN) as client:
        yield client, application


def send(client, text, version, request_id=None):
    return client.post(
        "/api/v1/turns",
        json={"text": text, "expected_version": version, "request_id": request_id or str(uuid4())},
    )


def test_session_cookie_and_safe_initial_view(app):
    client, _ = app
    response = client.post("/api/v1/session")
    assert response.status_code == 200
    assert response.json()["version"] == 0
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=strict" in response.headers["set-cookie"].lower()
    assert client.get("/api/v1/session").json() == response.json()
    assert "private_facts" not in response.text


def test_missing_cookie_is_unauthorized(app):
    client, _ = app
    assert client.get("/api/v1/session").status_code == 401


def test_origin_and_body_limits(app):
    client, _ = app
    assert (
        client.post("/api/v1/session", headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert client.post("/api/v1/session", content="x" * 17000).status_code == 413


@pytest.mark.parametrize("text", ["", "   ", "x" * 1001])
def test_invalid_turns_do_not_echo_input(app, text):
    client, _ = app
    client.post("/api/v1/session")
    response = send(client, text, 0)
    assert response.status_code == 422
    assert set(response.json()["error"]) == {"code", "message", "request_id"}


def test_identical_retry_replays_before_stale_version_check(app):
    client, _ = app
    client.post("/api/v1/session")
    identity = str(uuid4())
    first = send(client, "a black bag", 0, identity)
    retry = send(client, "a black bag", 0, identity)
    assert first.status_code == 200
    assert retry.json() == first.json()
    assert send(client, "a red bag", 0, identity).status_code == 409
    assert send(client, "a red bag", 0).status_code == 409


def test_other_session_has_its_own_state(app):
    client, application = app
    client.post("/api/v1/session")
    send(client, "black bag", 0)
    with TestClient(application, headers=ORIGIN) as other:
        other.post("/api/v1/session")
        assert other.get("/api/v1/session").json()["fields"]["category"] is None
        assert other.get("/api/v1/session").json()["version"] == 0


def test_report_is_durable_and_duplicate_confirmation_is_harmless(app):
    client, application = app
    client.post("/api/v1/session")
    proposal = send(client, "purple wallet with stars lost yesterday near the cinema", 0).json()
    # If more details are needed, explicitly decline to guess a brand.
    for _ in range(6):
        if proposal["state"] == "confirming":
            break
        proposal = send(client, "I don't know", proposal["version"]).json()
    assert proposal["proposal"] == "lost_report"
    assert proposal["receipt"] is None
    receipt = send(client, "yes", proposal["version"]).json()
    assert receipt["receipt"]["kind"] == "lost_report"
    assert receipt["receipt"]["status"] == "open"
    repeated = send(client, "yes", receipt["version"]).json()
    assert repeated["receipt"] == receipt["receipt"]
    with application.state.db.sessions() as db:
        assert db.scalar(select(func.count()).select_from(CaseRow)) == 1


def test_claim_keeps_private_facts_out_of_api_and_logs(app, caplog):
    client, _ = app
    client.post("/api/v1/session")
    response = send(client, "black backpack with two compartments food court yesterday", 0)
    assert response.status_code == 200
    assert response.json()["state"] == "identifying"
    assert "yellow duck" not in response.text
    assert "blue notebook" not in response.text
    identified = send(client, "yellow duck keychain", response.json()["version"]).json()
    assert identified["proposal"] == "claim"
    result = send(client, "yes", identified["version"]).json()
    assert result["receipt"]["status"] == "pending_review"
    assert "yellow duck" not in caplog.text
    assert "private_facts" not in str(result)


def test_two_concurrent_turns_cannot_overwrite_each_other(app):
    client, _ = app
    client.post("/api/v1/session")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda text: send(client, text, 0).status_code, ["black bag", "red bag"])
        )
    assert sorted(results) == [200, 409]


def test_delete_session_forgets_transcript(app):
    client, _ = app
    client.post("/api/v1/session")
    send(client, "black bag", 0)
    assert client.delete("/api/v1/session").status_code == 204
    assert client.get("/api/v1/session").status_code == 401


def test_health_does_not_disclose_configuration(app):
    client, _ = app
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}
    response = client.get("/health/live")
    assert response.headers["x-content-type-options"] == "nosniff"


def test_two_confirmed_searches_in_one_session_create_separate_cases(app):
    client, application = app
    client.post("/api/v1/session")
    snapshot = send(client, "purple wallet with stars yesterday", 0).json()
    snapshot = send(client, "yes", snapshot["version"]).json()
    first = snapshot["receipt"]["reference"]
    snapshot = send(client, "new search", snapshot["version"]).json()
    snapshot = send(client, "yes", snapshot["version"]).json()
    snapshot = send(client, "orange phone with stripes yesterday", snapshot["version"]).json()
    for _ in range(6):
        if snapshot["state"] == "confirming":
            break
        snapshot = send(client, "I don't know", snapshot["version"]).json()
    snapshot = send(client, "yes", snapshot["version"]).json()
    assert snapshot["receipt"]["reference"] != first
    with application.state.db.sessions() as db:
        assert db.scalar(select(func.count()).select_from(CaseRow)) == 2


def test_production_session_open_limit_is_enforced(app):
    client, _ = app
    for _ in range(5):
        assert client.post("/api/v1/session").status_code == 200
    assert client.post("/api/v1/session").status_code == 429


def test_tampered_cookie_cannot_read_a_session(app):
    client, _ = app
    client.cookies.set("riverside_session", "invented-capability", path="/api")
    assert client.get("/api/v1/session").status_code == 401
