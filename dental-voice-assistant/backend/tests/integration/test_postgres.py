"""Integration tests — require real Postgres (skipped otherwise).

Run after:
    docker compose up -d db
Then:
    cd backend && pytest -m integration
"""

from __future__ import annotations

import asyncio
from datetime import date, time, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Appointment, Base
from app.repositories import appointments as repo


def _is_postgres() -> bool:
    return settings.database_url.startswith("postgresql")


@pytest.fixture(autouse=True)
def require_postgres() -> None:
    if not _is_postgres():
        pytest.skip("Postgres not configured (set DATABASE_URL to a postgresql:// URL)")


@pytest.fixture
async def pg_engine():
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def pg_session_factory(pg_engine):
    return async_sessionmaker(pg_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_table_created(pg_engine) -> None:
    assert _is_postgres()
    async with pg_engine.connect() as conn:
        res = await conn.execute(select(1))
        assert res.scalar() == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_concurrency_only_one_wins(pg_session_factory) -> None:
    """10 parallel book() calls on Postgres for the exact same slot -> exactly one succeeds."""
    test_day = date.today() + timedelta(days=2)
    start_t = time(10, 0)
    end_t = time(10, 30)

    async def book_one(i: int) -> Appointment | None:
        async with pg_session_factory() as session:
            appt = Appointment(
                patient_name=f"Patient {i}",
                patient_phone=f"0300123456{i}",
                service="checkup",
                appointment_date=test_day,
                start_time=start_t,
                end_time=end_t,
            )
            return await repo.create(session, appt)

    results = await asyncio.gather(*[book_one(i) for i in range(10)], return_exceptions=True)

    successes = [r for r in results if isinstance(r, Appointment)]
    failures = [r for r in results if r is None]

    assert len(successes) == 1
    assert len(failures) == 9
