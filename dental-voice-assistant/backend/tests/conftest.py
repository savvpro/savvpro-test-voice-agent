"""Shared pytest fixtures for all backend tests."""

from __future__ import annotations

import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.engine import get_session
from app.db.models import Base
from app.main import create_app

# Ensure ai-tool/src is in sys.path
_AI_TOOL_SRC = str(Path(__file__).resolve().parent.parent.parent / "ai-tool" / "src")
if _AI_TOOL_SRC not in sys.path:
    sys.path.insert(0, _AI_TOOL_SRC)

# ── In-memory SQLite engine for tests ────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_engine(tmp_path):  # type: ignore[return]
    db_file = tmp_path / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:  # type: ignore[return]
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:  # type: ignore[return]
    """Return an httpx AsyncClient bound to the test app with test DB."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session  # type: ignore[misc]

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c
