"""HTTP contract tests for session lifecycle and turn processing."""

from __future__ import annotations


def test_create_session_returns_greeting_and_starts_tracking(api_services):
    client, _, store = api_services
    response = client.post("/sessions")

    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "COLLECT_TRACKING_ID"
    assert "tracking ID" in body["greeting"]
    assert store.get_session(body["session_id"]) is not None


def test_turn_and_history_round_trip(api_services):
    client, _, _ = api_services
    session_id = client.post("/sessions").json()["session_id"]

    turn = client.post(f"/sessions/{session_id}/turns", json={"text": "RD30000001"})
    history = client.get(f"/sessions/{session_id}")

    assert turn.status_code == 200
    assert turn.json()["trace"]["state_after"] == "CONFIRM_TRACKING_ID"
    assert history.status_code == 200
    assert history.json()["state"] == "CONFIRM_TRACKING_ID"
    assert len(history.json()["turns"]) == 3


def test_empty_text_is_silence(api_services):
    client, _, _ = api_services
    session_id = client.post("/sessions").json()["session_id"]

    response = client.post(f"/sessions/{session_id}/turns", json={"text": ""})

    assert response.status_code == 200
    assert response.json()["trace"]["state_after"] == "COLLECT_TRACKING_ID"
    assert "hear" in response.json()["reply"].lower()


def test_low_stt_confidence_reasks(api_services):
    client, _, _ = api_services
    session_id = client.post("/sessions").json()["session_id"]

    response = client.post(
        f"/sessions/{session_id}/turns",
        json={"text": "RD30000001", "stt_confidence": 0.2},
    )

    assert response.status_code == 200
    assert response.json()["trace"]["state_after"] == "COLLECT_TRACKING_ID"
    assert "catch that" in response.json()["reply"].lower()


def test_delete_ends_session_and_rejects_future_turns(api_services):
    client, _, _ = api_services
    session_id = client.post("/sessions").json()["session_id"]

    assert client.delete(f"/sessions/{session_id}").status_code == 204
    history = client.get(f"/sessions/{session_id}")
    assert history.status_code == 200
    assert history.json()["ended"] is True
    turn = client.post(f"/sessions/{session_id}/turns", json={"text": "hello"})
    assert turn.status_code == 200
    assert turn.json()["ended"] is True
    assert "ended" in turn.json()["reply"].lower()


def test_turn_request_rejects_oversized_text(api_services):
    client, _, _ = api_services
    session_id = client.post("/sessions").json()["session_id"]

    response = client.post(
        f"/sessions/{session_id}/turns", json={"text": "x" * 2001}
    )

    assert response.status_code == 422
