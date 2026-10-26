"""Tests for API route endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Create an async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.anyio
async def test_health_check_returns_200(client):
    """Health check endpoint should return 200 OK."""
    response = await client.get("/api/health")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_health_check_response_body(client):
    """Health check should return correct status, service name, and version."""
    response = await client.get("/api/health")
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "voice-assistant-api"
    assert data["version"] == "0.1.0"


@pytest.mark.anyio
async def test_health_check_content_type(client):
    """Health check should return JSON content type."""
    response = await client.get("/api/health")
    assert response.headers["content-type"] == "application/json"


@pytest.mark.anyio
async def test_unknown_route_returns_404(client):
    """Requests to unknown routes should return 404."""
    response = await client.get("/api/nonexistent")
    assert response.status_code == 404
