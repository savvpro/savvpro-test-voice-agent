from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from tests.conftest import start


def test_stt_disabled_is_explicit(client: TestClient) -> None:
    start(client)
    client.app.state.settings.groq_api_key = SecretStr("")
    assert not client.get("/api/capabilities").json()["server_stt"]
    result = client.post(
        "/api/stt", files={"audio": ("turn.webm", b"\x1aE\xdf\xa3audio", "audio/webm")}
    )
    assert result.status_code == 503


@pytest.mark.parametrize(
    ("content", "mime", "expected"),
    [
        (b"no audio", "text/plain", 415),
        (b"not audio", "audio/webm", 415),
        (b"", "audio/webm", 413),
        (b"x" * (5 * 1024 * 1024 + 1), "audio/webm", 413),
    ],
    ids=["wrong-mime", "invalid-header", "empty", "oversized"],
)
def test_stt_validates_audio(client: TestClient, content: bytes, mime: str, expected: int) -> None:
    start(client)
    client.app.state.settings.groq_api_key = SecretStr("test-only-not-a-real-key")
    result = client.post("/api/stt", files={"audio": ("turn.webm", content, mime)})
    assert result.status_code == expected


def test_stt_is_transcription_only(client: TestClient) -> None:
    initial = start(client)
    client.app.state.settings.groq_api_key = SecretStr("test-only-not-a-real-key")
    provider = AsyncMock()
    provider.post.return_value = httpx.Response(200, json={"text": "Book an oil change for my car"})
    manager = AsyncMock()
    manager.__aenter__.return_value = provider
    with patch("backend.app.httpx.AsyncClient", return_value=manager):
        result = client.post(
            "/api/stt", files={"audio": ("turn.webm", b"\x1aE\xdf\xa3audio", "audio/webm")}
        )
    assert result.json() == {"text": "Book an oil change for my car"}
    assert provider.post.call_args.kwargs["data"]["model"] == "whisper-large-v3-turbo"
    assert start(client) == initial


@pytest.mark.parametrize(
    ("status", "body", "expected"), [(429, {}, 429), (500, {}, 502), (200, {"text": ""}, 422)]
)
def test_stt_provider_failures(
    client: TestClient, status: int, body: dict[str, Any], expected: int
) -> None:
    start(client)
    client.app.state.settings.groq_api_key = SecretStr("test-only-not-a-real-key")
    provider = AsyncMock()
    provider.post.return_value = httpx.Response(status, json=body)
    manager = AsyncMock()
    manager.__aenter__.return_value = provider
    with patch("backend.app.httpx.AsyncClient", return_value=manager):
        result = client.post(
            "/api/stt", files={"audio": ("turn.webm", b"\x1aE\xdf\xa3audio", "audio/webm")}
        )
    assert result.status_code == expected
