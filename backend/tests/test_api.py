from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from app import main
from app.brain import TZ


def ready(client, dining="a la carte", seating="indoor", adults=4):
    data = client.post("/api/sessions").json()
    sid = data["session_id"]
    day = datetime.now(TZ).date() + timedelta(days=7)
    while day.weekday() != 4:
        day += timedelta(days=1)
    values = [
        dining,
        day.isoformat(),
        "6 PM",
        f"{adults} adults",
        "no children",
        seating,
        "name is Demo Guest",
        "03000000000",
    ]
    for i, text in enumerate(values):
        result = client.post(
            f"/api/sessions/{sid}/turns", json={"text": text, "request_id": str(i)}
        )
        assert result.status_code == 200
    assert result.json()["state"]["stage"] == "review"
    return sid


def send(client, sid, text, key="confirm"):
    return client.post(
        f"/api/sessions/{sid}/turns", json={"text": text, "request_id": key}
    ).json()


def test_booking_idempotency_and_cancel(client):
    sid = ready(client)
    first = send(client, sid, "yes")
    retry = send(client, sid, "yes")
    assert first == retry
    assert first["state"]["booking"]["status"] == "confirmed"
    send(client, sid, "cancel", "cancel")
    done = send(client, sid, "yes", "cancel-yes")
    assert done["state"]["booking"]["status"] == "cancelled"


def test_buffet_payment_and_spoken_claim(client):
    sid = ready(client, "hi-tea")
    result = send(client, sid, "yes")
    assert result["state"]["stage"] == "payment_pending"
    assert (
        send(client, sid, "I have paid", "paid")["state"]["rule"]
        == "payment_verification_required"
    )
    assert (
        client.post(f"/api/sessions/{sid}/demo-payment").json()["state"]["stage"]
        == "confirmed"
    )


def test_expired_hold_cannot_be_paid(client):
    sid = ready(client, "hi-tea")
    send(client, sid, "yes")
    with main.store.connection() as db:
        db.execute("UPDATE bookings SET expires='2000-01-01T00:00:00+05:00'")
    assert client.post(f"/api/sessions/{sid}/demo-payment").status_code == 409


def test_concurrent_last_tables(client):
    sessions = [ready(client, adults=12) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda sid: send(client, sid, "yes"), sessions))
    assert sum(r["state"]["stage"] == "confirmed" for r in results) == 1
    assert sum(r["state"]["rule"] == "capacity_unavailable" for r in results) == 1


def test_failed_amendment_keeps_original(client):
    other = ready(client, seating="rooftop", adults=12)
    send(client, other, "yes")
    sid = ready(client)
    original = send(client, sid, "yes")["state"]["booking"]["id"]
    send(client, sid, "rooftop", "change")
    rejected = send(client, sid, "yes", "reconfirm")
    assert rejected["state"]["rule"] == "capacity_unavailable"
    with main.store.connection() as db:
        assert (
            db.execute(
                "SELECT status FROM bookings WHERE id=?", (original,)
            ).fetchone()[0]
            == "confirmed"
        )


def test_child_capacity_counts_and_adjacent_times(client):
    sid = ready(client, adults=12)
    send(client, sid, "yes")
    next_sid = ready(client)
    send(client, next_sid, "8 PM", "time")
    assert send(client, next_sid, "yes")["state"]["stage"] == "confirmed"


def test_validation(client):
    assert (
        client.post(
            "/api/sessions/missing/turns", json={"text": "yes", "request_id": "x"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/sessions/missing/turns", json={"text": "", "request_id": "x"}
        ).status_code
        == 422
    )
