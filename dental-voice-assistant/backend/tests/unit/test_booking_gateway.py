"""Unit tests for ClinicRules and SqlBookingGateway."""

from __future__ import annotations

from datetime import date, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from voice_agent.ports import BookingGateway  # type: ignore[import-not-found]

from app.db.engine import create_async_engine
from app.db.models import Base
from app.services.booking_gateway import ClinicRules, SqlBookingGateway


def _next_open_day() -> date:
    d = date.today() + timedelta(days=1)
    while d.weekday() == 6:  # skip Sunday
        d += timedelta(days=1)
    return d


def test_clinic_rules_slots():
    rules = ClinicRules(
        open_hour=9,
        close_hour=11,
        slot_minutes=30,
        open_weekdays=[0, 1, 2, 3, 4, 5],
    )
    open_day = _next_open_day()
    slots = rules.all_slots(open_day)
    assert len(slots) == 4
    assert slots[0].start == time(9, 0)
    assert slots[0].end == time(9, 30)
    assert slots[-1].start == time(10, 30)
    assert slots[-1].end == time(11, 0)


def test_clinic_rules_closed_on_sunday():
    rules = ClinicRules(open_weekdays=[0, 1, 2, 3, 4, 5])
    # Find next Sunday
    d = date.today()
    while d.weekday() != 6:
        d += timedelta(days=1)
    slots = rules.all_slots(d)
    assert slots == []


def test_protocol_compliance():
    dummy_factory = async_sessionmaker()
    gw = SqlBookingGateway(session_factory=dummy_factory)
    assert isinstance(gw, BookingGateway)


def test_gateway_crud_sync(tmp_path):
    """Test SqlBookingGateway methods from synchronous execution."""
    db_file = tmp_path / "gw_test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    import asyncio

    async def _init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init_db())

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    gw = SqlBookingGateway(session_factory=factory)

    test_day = _next_open_day()

    # 1. free slots
    free = gw.free_slots(test_day)
    assert len(free) > 0

    slot = free[0]

    # 2. book
    booking_id = gw.book("Test Patient", "03001234567", "cleaning", slot)
    assert booking_id is not None

    # 3. duplicate book fails
    dup = gw.book("Other Patient", "03007654321", "whitening", slot)
    assert dup is None

    # 4. find upcoming by phone
    upcoming = gw.find_upcoming_by_phone("03001234567")
    assert len(upcoming) == 1
    assert upcoming[0][0] == booking_id
    assert upcoming[0][1].start == slot.start

    # 5. reschedule
    new_slot = free[1]
    rescheduled_id = gw.reschedule(booking_id, new_slot)
    assert rescheduled_id is not None
    assert rescheduled_id != booking_id

    # 6. cancel
    cancelled = gw.cancel(rescheduled_id)
    assert cancelled is True

    # 7. cancel already cancelled returns False
    cancelled_again = gw.cancel(rescheduled_id)
    assert cancelled_again is False

    asyncio.run(engine.dispose())
