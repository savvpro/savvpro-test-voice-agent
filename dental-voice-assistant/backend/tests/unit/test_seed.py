"""Unit tests for app.db.seed."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.engine import create_async_engine
from app.db.models import Appointment, Base
from app.db.seed import seed


@pytest.mark.asyncio
async def test_seed_creates_appointments_and_is_idempotent(tmp_path):
    db_file = tmp_path / "seed_test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # First run
    async with factory() as session:
        await seed(session)

    # Verify ~15 appointments created
    async with factory() as session:
        result = await session.execute(select(Appointment).where(Appointment.status == "confirmed"))
        appts = list(result.scalars())
        assert len(appts) >= 15

    # Second run should be idempotent
    async with factory() as session:
        await seed(session)

    async with factory() as session:
        result = await session.execute(select(Appointment).where(Appointment.status == "confirmed"))
        appts2 = list(result.scalars())
        assert len(appts2) == len(appts)

    await engine.dispose()
