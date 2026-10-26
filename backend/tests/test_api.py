from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import dialogue
from app.main import create_app
from tests.conftest import NOW


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(":memory:")
    with TestClient(app) as c:
        app.state.clock = lambda: NOW
        c.app = app
        yield c


def start(c: TestClient) -> str:
    r = c.post("/api/calls")
    assert r.status_code == 201
    return str(r.json()["call_id"])


def turn(c: TestClient, cid: str, text: str):  # type: ignore[no-untyped-def]
    return c.post(f"/api/calls/{cid}/turns", json={"text": text})


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_start_call_returns_greeting(client: TestClient) -> None:
    r = client.post("/api/calls")
    body = r.json()
    assert r.status_code == 201
    assert "Maple Street Clinic" in body["reply"]
    assert body["decision"]["action"] == "greet" and body["ended"] is False


def test_full_booking_over_http(client: TestClient) -> None:
    cid = start(client)
    actions = [
        turn(client, cid, t).json()["decision"]["action"]
        for t in (
            "Hi, I want to book with Dr Patel tomorrow at 2pm, my name is Sara Lee",
            "March 4 1990",
            "yes",
        )
    ]
    assert actions == ["ask_dob", "confirm_booking", "booked"]


def test_unknown_call_404(client: TestClient) -> None:
    r = turn(client, "nope", "hi")
    assert r.status_code == 404 and r.json() == {"detail": "Call not found or expired"}


def test_expired_call_404(client: TestClient) -> None:
    cid = start(client)
    client.app.state.clock = lambda: NOW + timedelta(minutes=31)  # type: ignore[attr-defined]
    assert turn(client, cid, "hi").status_code == 404


def test_not_expired_within_30_min(client: TestClient) -> None:
    cid = start(client)
    client.app.state.clock = lambda: NOW + timedelta(minutes=29)  # type: ignore[attr-defined]
    assert turn(client, cid, "hi").status_code == 200


def test_ended_call_404(client: TestClient) -> None:
    cid = start(client)
    r = turn(client, cid, "I'm having chest pain")
    assert r.json()["ended"] is True
    assert turn(client, cid, "hello").status_code == 404


def test_text_too_long_422(client: TestClient) -> None:
    cid = start(client)
    assert turn(client, cid, "a" * 501).status_code == 422


def test_empty_text_reprompts(client: TestClient) -> None:
    cid = start(client)
    r = turn(client, cid, "")
    assert r.status_code == 200 and r.json()["decision"]["action"] == "reprompt"


def test_internal_error_is_500_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    cid = start(client)

    def boom(*a: object, **k: object) -> None:
        raise RuntimeError("secret")

    monkeypatch.setattr(dialogue, "handle_turn", boom)
    r = turn(client, cid, "hi")
    assert r.status_code == 500 and r.json() == {"detail": "Internal error"}
    assert "secret" not in r.text and cid in caplog.text
