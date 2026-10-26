"""The HTTP API end to end, with fake speech engines and an in-memory clinic."""

import base64
from datetime import date

from fastapi.testclient import TestClient

from app.main import create_app
from tests.fakes import FAKE_WAV, BrokenSTT, BrokenTTS


def start(client) -> dict:
    response = client.post("/api/sessions")
    assert response.status_code == 201
    return response.json()


def say(client, session_id: str, text: str) -> dict:
    response = client.post(f"/api/sessions/{session_id}/turn", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


def test_full_booking_by_text(client):
    greeting = start(client)
    sid = greeting["session_id"]
    assert "Shifa Care Clinic" in greeting["reply_text"]
    assert greeting["transcript"] is None and greeting["nlu"] is None
    assert greeting["decision"]["state"] == "IDENTIFY_TASK"

    turn = say(client, sid, "I'd like to book a cardiologist on Friday at 11 am")
    assert turn["transcript"] == "I'd like to book a cardiologist on Friday at 11 am"
    assert turn["nlu"]["entities"]["department"] == "Cardiology"
    assert turn["decision"]["frame"]["chosen_slot"]["start"] == "2030-01-11T11:00:00"
    say(client, sid, "Sana Malik")
    turn = say(client, sid, "0321 7654321")
    assert turn["decision"]["state"] == "CONFIRM"
    turn = say(client, sid, "yes please")

    assert turn["decision"]["action"] == "booked"
    ref = turn["decision"]["frame"]["booking_ref"]
    assert ref and ref.startswith("SC-")
    assert set(turn["timings_ms"]) == {"stt", "nlu", "dm", "tts"}

    [booked] = client.get("/api/admin/appointments").json()
    assert booked == {
        "booking_ref": ref,
        "patient_name": "Sana Malik",
        "phone": "0321****321",
        "start": "2030-01-11T11:00:00",
        "doctor": booked["doctor"],
        "department": "Cardiology",
        "status": "booked",
    }

    recent = client.get("/api/admin/appointments", params={"order": "recent"}).json()
    assert recent[0]["booking_ref"] == ref

    session = client.get(f"/api/sessions/{sid}").json()
    assert [h["role"] for h in session["history"]] == ["agent"] + ["caller", "agent"] * 4
    assert session["frame"]["booking_ref"] == ref
    assert session["ended"] is False


def test_reply_audio_is_base64_wav(client):
    greeting = start(client)
    assert base64.b64decode(greeting["audio_base64"]) == FAKE_WAV
    assert greeting["audio_mime"] == "audio/wav"


def test_audio_turn_is_transcribed(client):
    sid = start(client)["session_id"]
    response = client.post(
        f"/api/sessions/{sid}/turn",
        files={"audio": ("turn.webm", b"what time do you open on saturday", "audio/webm")},
    )
    assert response.status_code == 200, response.text
    turn = response.json()
    assert turn["transcript"] == "what time do you open on saturday"
    assert turn["transcript_confidence"] == 0.9
    assert turn["nlu"]["intent"] == "clinic_hours"
    assert turn["timings_ms"]["stt"] >= 0


def test_audio_without_speech_engine_is_503(make_conversation):
    with TestClient(create_app(make_conversation(stt=None))) as client:
        sid = start(client)["session_id"]
        response = client.post(f"/api/sessions/{sid}/turn", files={"audio": ("a.webm", b"x")})
        assert response.status_code == 503
        assert "send text" in response.json()["detail"]
        # text still works
        assert say(client, sid, "where are you located")["nlu"]["intent"] == "clinic_location"


def test_unreadable_audio_is_422(make_conversation):
    with TestClient(create_app(make_conversation(stt=BrokenSTT()))) as client:
        sid = start(client)["session_id"]
        response = client.post(f"/api/sessions/{sid}/turn", files={"audio": ("a.webm", b"x")})
        assert response.status_code == 422
        assert response.json()["detail"] == "could not read the audio"


def test_multipart_without_audio_field_is_422(client):
    sid = start(client)["session_id"]
    response = client.post(f"/api/sessions/{sid}/turn", files={"recording": ("a.webm", b"x")})
    assert response.status_code == 422
    assert response.json()["detail"] == "multipart request needs an 'audio' file"


def test_failing_tts_still_returns_text(make_conversation):
    with TestClient(create_app(make_conversation(tts=BrokenTTS()))) as client:
        greeting = start(client)
        assert greeting["reply_text"]
        assert greeting["audio_base64"] is None and greeting["audio_mime"] is None


def test_bad_json_is_422(client):
    sid = start(client)["session_id"]
    response = client.post(
        f"/api/sessions/{sid}/turn",
        content=b'{"text": 5}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422


def test_empty_text_is_silence(client):
    sid = start(client)["session_id"]
    turn = say(client, sid, "")
    assert turn["decision"]["action"] == "silence"
    assert turn["transcript"] == ""


def test_unknown_session_is_404(client):
    assert client.post("/api/sessions/nope/turn", json={"text": "hi"}).status_code == 404
    assert client.get("/api/sessions/nope").status_code == 404


def test_call_ends_and_stays_ended(client):
    sid = start(client)["session_id"]
    turn = say(client, sid, "bye")
    assert turn["decision"]["end_call"] is True
    assert client.get(f"/api/sessions/{sid}").json()["ended"] is True
    assert say(client, sid, "hello?")["decision"]["end_call"] is True


def test_emergency_over_the_api(client):
    sid = start(client)["session_id"]
    turn = say(client, sid, "my father has chest pain and can't breathe")
    assert turn["decision"]["action"] == "emergency"
    assert "1122" in turn["reply_text"]


def test_admin_slots_filtered_by_department_and_date(client):
    slots = client.get("/api/admin/slots", params={"department": "ENT", "date": "2030-01-12"})
    body = slots.json()
    assert slots.status_code == 200 and body
    assert {s["department"] for s in body} == {"ENT"}
    assert {date.fromisoformat(s["start"][:10]) for s in body} == {date(2030, 1, 12)}
    assert not any(s["is_booked"] for s in body)


def test_admin_slots_rejects_bad_date(client):
    assert client.get("/api/admin/slots", params={"date": "friday"}).status_code == 422


def test_cors_allows_frontend_origin(client):
    response = client.options(
        "/api/sessions",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
