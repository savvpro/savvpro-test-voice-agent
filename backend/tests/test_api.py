def test_health(client) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_submit_turn(client) -> None:
    created = client.post("/api/conversations").json()
    response = client.post(
        f"/api/conversations/{created['conversation_id']}/turns",
        json={"turn_id": "t1", "expected_version": 0, "transcript": "Sara Khan"},
    )
    assert response.status_code == 200
    assert response.json()["pending_field"] == "phone"


def test_api_rejects_stale_turn(client) -> None:
    created = client.post("/api/conversations").json()
    url = f"/api/conversations/{created['conversation_id']}/turns"
    assert client.post(url, json={"turn_id": "t1", "expected_version": 0, "transcript": "Sara"}).status_code == 200
    assert (
        client.post(url, json={"turn_id": "t2", "expected_version": 0, "transcript": "5551234567"}).status_code == 409
    )


def test_logs_redact_phone_numbers(client, caplog) -> None:
    created = client.post("/api/conversations").json()
    client.post(
        f"/api/conversations/{created['conversation_id']}/turns",
        json={
            "turn_id": "phone",
            "expected_version": 0,
            "transcript": "5551234567",
        },
    )
    assert "5551234567" not in caplog.text
