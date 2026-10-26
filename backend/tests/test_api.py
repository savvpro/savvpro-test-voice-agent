"""Tests for API routes."""

import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_start_conversation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/conversation/start")
    assert response.status_code == 200
    data = response.json()
    assert "conversation_id" in data
    assert "response" in data
    assert "Welcome" in data["response"]


@pytest.mark.asyncio
async def test_send_message():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Start conversation
        start = await client.post("/api/conversation/start")
        conv_id = start.json()["conversation_id"]

        # Send message
        response = await client.post("/api/message", json={
            "conversation_id": conv_id,
            "text": "tomorrow",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == conv_id


@pytest.mark.asyncio
async def test_send_message_invalid_conv():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/message", json={
            "conversation_id": "nonexistent",
            "text": "hello",
        })
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_conversation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start = await client.post("/api/conversation/start")
        conv_id = start.json()["conversation_id"]

        response = await client.get(f"/api/conversation/{conv_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == conv_id
    assert len(data["turns"]) > 0
