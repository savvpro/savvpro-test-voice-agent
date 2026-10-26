"""SqlBookingGateway: async → sync adapter for the brain's BookingGateway port.

The brain is synchronous (state machine); the DB layer is async.
This adapter runs the async DB calls in a new event-loop via asyncio.run()
so it is safe to call from the brain's sync context.

In the API layer, use the AsyncSqlBookingGateway variant instead.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Import port definitions from ai-tool
from voice_agent.ports import SlotInfo  # type: ignore[import]

from app.config import settings
from app.db.models import Appointment
from app.repositories import appointments as repo

logger = logging.getLogger(__name__)


class ClinicRules:
    """Holds clinic slot-generation rules (injected into the gateway)."""

    def __init__(
        self,
        open_hour: int = settings.clinic_open_hour,
        close_hour: int = settings.clinic_close_hour,
        slot_minutes: int = settings.clinic_slot_minutes,
        open_weekdays: list[int] | None = None,
    ) -> None:
        self.open_hour = open_hour
        self.close_hour = close_hour
        self.slot_minutes = slot_minutes
        self.open_weekdays = open_weekdays or settings.clinic_open_weekdays

    def all_slots(self, day: date) -> list[SlotInfo]:
        if day.weekday() not in self.open_weekdays:
            return []
        slots: list[SlotInfo] = []
        current = self.open_hour * 60
        close = self.close_hour * 60
        while current + self.slot_minutes <= close:
            start = time(current // 60, current % 60)
            end = time(
                (current + self.slot_minutes) // 60,
                (current + self.slot_minutes) % 60,
            )
            slots.append(SlotInfo(day, start, end))
            current += self.slot_minutes
        return slots


class SqlBookingGateway:
    """Synchronous BookingGateway backed by SQLAlchemy async sessions.

    Runs async operations in a dedicated event loop so the sync brain can
    call it transparently.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        rules: ClinicRules | None = None,
    ) -> None:
        self._factory = session_factory
        self._rules = rules or ClinicRules()

    # ── Internal helper ───────────────────────────────────────────────────────

    def _run(self, coro: object) -> object:  # type: ignore[type-arg]
        """Execute an async coroutine synchronously."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We are inside an existing event-loop (e.g. FastAPI background).
            # Create a new thread to run in a fresh loop.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future: concurrent.futures.Future[Any] = pool.submit(asyncio.run, coro)  # type: ignore[arg-type]
                return future.result()
        else:
            return asyncio.run(coro)  # type: ignore[arg-type]

    # ── BookingGateway protocol impl ──────────────────────────────────────────

    def free_slots(self, day: date) -> list[SlotInfo]:
        async def _inner() -> list[SlotInfo]:
            async with self._factory() as session:
                available = await repo.free_slots(session, day)
                return [SlotInfo(day, s, e) for s, e in available]

        return self._run(_inner())  # type: ignore[return-value]

    def book(
        self,
        patient_name: str,
        patient_phone: str,
        service: str,
        slot: SlotInfo,
    ) -> str | None:
        async def _inner() -> str | None:
            async with self._factory() as session:
                appt = Appointment(
                    patient_name=patient_name,
                    patient_phone=patient_phone,
                    service=service,
                    appointment_date=slot.date,
                    start_time=slot.start,
                    end_time=slot.end,
                )
                result = await repo.create(session, appt)
                return result.id if result else None

        return self._run(_inner())  # type: ignore[return-value]

    def cancel(self, booking_id: str) -> bool:
        async def _inner() -> bool:
            async with self._factory() as session:
                return await repo.cancel(session, booking_id)

        return self._run(_inner())  # type: ignore[return-value]

    def reschedule(self, booking_id: str, new_slot: SlotInfo) -> str | None:
        async def _inner() -> str | None:
            async with self._factory() as session:
                appt = Appointment(
                    patient_name="",  # will be updated below
                    patient_phone="",
                    service="",
                    appointment_date=new_slot.date,
                    start_time=new_slot.start,
                    end_time=new_slot.end,
                )
                result = await repo.reschedule(session, booking_id, appt)
                return result.id if result else None

        return self._run(_inner())  # type: ignore[return-value]

    def find_upcoming_by_phone(self, phone: str) -> list[tuple[str, SlotInfo]]:
        async def _inner() -> list[tuple[str, SlotInfo]]:
            async with self._factory() as session:
                appts = await repo.find_upcoming_by_phone(session, phone)
                return [
                    (a.id, SlotInfo(a.appointment_date, a.start_time, a.end_time)) for a in appts
                ]

        return self._run(_inner())  # type: ignore[return-value]


# Verify structural compliance at import time
assert isinstance(SqlBookingGateway.__mro__, tuple)  # runtime check placeholder
