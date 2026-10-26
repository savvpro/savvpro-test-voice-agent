from datetime import timedelta

from app.brain import advance
from test_api import ready, send
from test_brain import NOW, complete, say


def test_unclear_correction_blocks_old_confirmation():
    s = complete()
    say(s, "2 children")
    assert s["stage"] == "collecting"
    assert say(s, "yes") != "BOOK_ACTION"
    say(s, "children aged 3 and 7")
    assert s["stage"] == "review"


def test_invalid_date_cannot_confirm_old_date():
    s = complete()
    say(s, "2026-02-30")
    assert say(s, "yes") != "BOOK_ACTION"


def test_confirmation_revalidates_arrival_time():
    s = complete()
    assert advance(s, "yes", NOW + timedelta(days=20)) != "BOOK_ACTION"
    assert s["rule"] == "past_time"


def test_cancel_requires_explicit_answer(client):
    sid = ready(client, "hi-tea")
    send(client, sid, "yes")
    send(client, sid, "cancel", "cancel")
    assert (
        send(client, sid, "maybe", "maybe")["state"]["stage"] == "cancel_confirmation"
    )
    assert send(client, sid, "no", "no")["state"]["stage"] == "payment_pending"


def test_request_id_cannot_be_reused_for_other_text(client):
    sid = ready(client)
    send(client, sid, "yes")
    response = client.post(
        f"/api/sessions/{sid}/turns", json={"text": "cancel", "request_id": "confirm"}
    )
    assert response.status_code == 409


def test_unchanged_booking_does_not_reenter_review(client):
    sid = ready(client)
    send(client, sid, "yes")
    assert send(client, sid, "hello", "hello")["state"]["stage"] == "confirmed"


def test_full_area_offers_verified_alternatives(client):
    first = ready(client, adults=12)
    send(client, first, "yes")
    second = ready(client)
    rejected = send(client, second, "yes")
    assert rejected["state"]["alternatives"]
    option = rejected["state"]["alternatives"][0]
    assert option == {"time": 1080, "seating": "rooftop"}
    send(client, second, "18:00 rooftop", "alternative")
    assert send(client, second, "yes", "accept")["state"]["stage"] == "confirmed"


def test_blank_input_is_rejected(client):
    sid = client.post("/api/sessions").json()["session_id"]
    assert (
        client.post(
            f"/api/sessions/{sid}/turns", json={"text": "   ", "request_id": "blank"}
        ).status_code
        == 422
    )
