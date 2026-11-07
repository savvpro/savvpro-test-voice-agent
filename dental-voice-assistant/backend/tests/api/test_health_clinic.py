"""API tests — health, clinic, appointments using httpx AsyncClient."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_clinic_info(client: AsyncClient) -> None:
    r = await client.get("/clinic")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "BrightSmile Dental Clinic"
    assert data["open_hour"] == 9
    assert data["close_hour"] == 17
    assert "cleaning" in data["services"]


@pytest.mark.asyncio
async def test_app_lifespan() -> None:
    from app.main import create_app, lifespan

    app = create_app()
    async with lifespan(app):
        pass
