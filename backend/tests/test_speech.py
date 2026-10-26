import httpx
import pytest
from fastapi.testclient import TestClient

from lost_property.config import Settings
from lost_property.main import create_app
from lost_property.persistence.database import Database

AUDIO = b"\x1a\x45\xdf\xa3" + b"\x00" * 128


def client_for(tmp_path, handler, key="test-only-key"):
    url = f"sqlite:///{(tmp_path / 'voice.db').as_posix()}"
    db = Database(url)
    db.migrate()
    db.engine.dispose()
    settings = Settings(database_url=url, allowed_origins=("http://testserver",), groq_api_key=key)
    app = create_app(settings, speech_transport=httpx.MockTransport(handler))
    return TestClient(app, headers={"Origin": "http://testserver"})


def test_groq_upload_uses_whisper_large_v3_and_keeps_key_server_side(tmp_path):
    received = []

    def upstream(request):
        received.append(request)
        assert request.url == "https://api.groq.com/openai/v1/audio/transcriptions"
        assert request.headers["authorization"] == "Bearer test-only-key"
        assert b"whisper-large-v3" in request.content
        assert AUDIO in request.content
        return httpx.Response(
            200, json={"text": "A black backpack near the food court.", "segments": []}
        )

    with client_for(tmp_path, upstream) as client:
        client.post("/api/v1/session")
        response = client.post(
            "/api/v1/transcriptions",
            content=AUDIO,
            headers={"Content-Type": "audio/webm;codecs=opus"},
        )
        assert response.status_code == 200
        assert response.json() == {"text": "A black backpack near the food court."}
        assert "test-only-key" not in response.text
        assert client.get("/api/v1/session").json()["version"] == 0
        assert len(received) == 1


@pytest.mark.parametrize("status,expected", [(401, 503), (429, 429), (400, 422), (500, 503)])
def test_provider_failures_are_safe_and_do_not_change_conversation(tmp_path, status, expected):
    def upstream(_):
        return httpx.Response(status, json={"error": {"message": "SENSITIVE_UPSTREAM_DETAIL"}})

    with client_for(tmp_path, upstream) as client:
        client.post("/api/v1/session")
        response = client.post(
            "/api/v1/transcriptions", content=AUDIO, headers={"Content-Type": "audio/webm"}
        )
        assert response.status_code == expected
        assert "SENSITIVE_UPSTREAM_DETAIL" not in response.text
        assert client.get("/api/v1/session").json()["version"] == 0


def test_silence_and_empty_transcripts_are_not_submitted(tmp_path):
    with client_for(
        tmp_path, lambda _: httpx.Response(200, json={"text": "", "segments": []})
    ) as client:
        client.post("/api/v1/session")
        assert (
            client.post(
                "/api/v1/transcriptions", content=AUDIO, headers={"Content-Type": "audio/webm"}
            ).status_code
            == 422
        )


def test_audio_requires_session_and_valid_container(tmp_path):
    with client_for(tmp_path, lambda _: httpx.Response(200, json={"text": "hello"})) as client:
        assert (
            client.post(
                "/api/v1/transcriptions", content=AUDIO, headers={"Content-Type": "audio/webm"}
            ).status_code
            == 401
        )
        client.post("/api/v1/session")
        assert (
            client.post(
                "/api/v1/transcriptions",
                content=b"not audio",
                headers={"Content-Type": "audio/webm"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/transcriptions", content=b"text", headers={"Content-Type": "text/plain"}
            ).status_code
            == 415
        )


def test_missing_key_has_useful_failure_without_contacting_groq(tmp_path):
    def forbidden(_):
        raise AssertionError("No external call is allowed without a configured key")

    with client_for(tmp_path, forbidden, key="") as client:
        client.post("/api/v1/session")
        response = client.post(
            "/api/v1/transcriptions", content=AUDIO, headers={"Content-Type": "audio/webm"}
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "VOICE_NOT_CONFIGURED"
