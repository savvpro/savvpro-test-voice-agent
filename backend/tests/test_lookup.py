from test_api import ready, send


def test_lookup_requires_matching_phone(client):
    sid = ready(client)
    booking = send(client, sid, "yes")["state"]["booking"]
    assert (
        client.post(
            "/api/bookings/lookup",
            json={"reference": booking["id"], "phone": "03111111111"},
        ).status_code
        == 404
    )
    found = client.post(
        "/api/bookings/lookup",
        json={"reference": booking["id"], "phone": "03000000000"},
    )
    assert found.status_code == 200
    assert found.json()["state"]["rule"] == "booking_verified"
