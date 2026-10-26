"""Async SQLAlchemy engine and session factory.

Import ``async_session_factory`` to get a session; use ``engine`` only for
migrations or direct DDL.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    # SQLite needs check_same_thread=False passed through connect_args
    connect_args=(
        {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    ),
    pool_pre_ping=True,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:  # FastAPI dependency
    """Yield an ``AsyncSession`` and close it when done."""
    async with async_session_factory() as session:
        yield session
