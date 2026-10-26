"""End-to-end API coverage for each supported parcel action."""

from __future__ import annotations


def _call(client, session_id: str, text: str) -> dict:
    response = client.post(f"/sessions/{session_id}/turns", json={"text": text})
    assert response.status_code == 200
    return response.json()


def _verified_call(client) -> str:
    session_id = client.post("/sessions").json()["session_id"]
    _call(client, session_id, "RD30000001")
    _call(client, session_id, "yes")
    _call(client, session_id, "1234")
    return session_id


def test_reschedule_call_reaches_booking_confirmation(api_services):
    client, repo, _ = api_services
    session_id = _verified_call(client)

    _call(client, session_id, "reschedule")
    date_reply = _call(client, session_id, "tomorrow afternoon")
    booked = _call(client, session_id, "yes")

    assert "shall i book" in date_reply["reply"].lower()
    assert booked["ended"] is False
    assert "say yes to continue" in booked["reply"].lower()
    assert repo.get_parcel("RD30000001").current_slot_id is not None
    assert _call(client, session_id, "no")["ended"] is True


def test_pickup_call_confirms_selected_point(api_services):
    client, _, _ = api_services
    session_id = _verified_call(client)

    _call(client, session_id, "pickup point")
    confirmation = _call(client, session_id, "Islamabad I-8 Markaz Depot")
    result = _call(client, session_id, "yes")

    assert "is that right" in confirmation["reply"].lower()
    assert result["ended"] is False
    assert "say yes to continue" in result["reply"].lower()
    assert "collect" in result["reply"].lower()
    assert _call(client, session_id, "no")["ended"] is True


def test_cancel_call_cancels_after_confirmation(api_services):
    client, repo, _ = api_services
    session_id = _verified_call(client)

    prompt = _call(client, session_id, "cancel")
    result = _call(client, session_id, "yes")

    assert "sure" in prompt["reply"].lower()
    assert result["ended"] is False
    assert "say yes to continue" in result["reply"].lower()
    assert repo.get_parcel("RD30000001").status.value == "cancelled"
    assert _call(client, session_id, "no")["ended"] is True
