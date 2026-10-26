"""Full API conversation through verification and a parcel status query."""

from __future__ import annotations


def test_status_call_completes_across_api_turns(api_services):
    client, _, _ = api_services
    session_id = client.post("/sessions").json()["session_id"]

    prompts = ["RD30000001", "yes", "1234", "where is my parcel"]
    responses = [
        client.post(f"/sessions/{session_id}/turns", json={"text": text})
        for text in prompts
    ]
    history = client.get(f"/sessions/{session_id}").json()

    assert all(response.status_code == 200 for response in responses)
    assert history["verified"] is True
    assert history["state"] == "ANYTHING_ELSE"
    assert "say yes to continue" in responses[-1].json()["reply"].lower()
    assert "failed attempt" in responses[-1].json()["reply"].lower()
