"""Shared fixtures and fake port implementations for ai-tool tests."""

from __future__ import annotations

from datetime import date, time

import pytest

from voice_agent.ports import SlotInfo


class FakeClock:
    """Deterministic Clock implementation for testing."""

    def __init__(self, current_date: date, current_time: time = time(9, 0)) -> None:
        self._date = current_date
        self._time = current_time

    def today(self) -> date:
        return self._date

    def now_time(self) -> time:
        return self._time


class FakeBookingGateway:
    """In-memory BookingGateway implementation for scenario testing."""

    def __init__(
        self,
        available_slots: dict[date, list[SlotInfo]] | None = None,
        existing_appointments: dict[str, list[tuple[str, SlotInfo]]] | None = None,
        fail_booking_on_slot: SlotInfo | None = None,
    ) -> None:
        self.available_slots = available_slots or {}
        self.existing_appointments = existing_appointments or {}
        self.fail_booking_on_slot = fail_booking_on_slot
        self.booked_ids: list[str] = []
        self.cancelled_ids: list[str] = []

    def free_slots(self, day: date) -> list[SlotInfo]:
        return list(self.available_slots.get(day, []))

    def book(
        self,
        patient_name: str,
        patient_phone: str,
        service: str,
        slot: SlotInfo,
    ) -> str | None:
        if self.fail_booking_on_slot and slot == self.fail_booking_on_slot:
            return None  # Simulate race condition: slot taken at confirmation

        # Remove from available
        day_slots = self.available_slots.get(slot.date, [])
        if slot in day_slots:
            day_slots.remove(slot)

        bid = f"booking-{len(self.booked_ids) + 1}"
        self.booked_ids.append(bid)
        self.existing_appointments.setdefault(patient_phone, []).append((bid, slot))
        return bid

    def cancel(self, booking_id: str) -> bool:
        self.cancelled_ids.append(booking_id)
        for _phone, appts in self.existing_appointments.items():
            for item in appts:
                if item[0] == booking_id:
                    appts.remove(item)
                    return True
        return False

    def reschedule(self, booking_id: str, new_slot: SlotInfo) -> str | None:
        if self.fail_booking_on_slot and new_slot == self.fail_booking_on_slot:
            return None

        # Remove old, add new
        self.cancel(booking_id)
        return self.book("Rescheduled Patient", "03001234567", "checkup", new_slot)

    def find_upcoming_by_phone(self, phone: str) -> list[tuple[str, SlotInfo]]:
        return list(self.existing_appointments.get(phone, []))


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock(date(2026, 10, 27))  # Tuesday


@pytest.fixture
def fake_gateway(fake_clock: FakeClock) -> FakeBookingGateway:
    # 2026-10-28 is Wednesday
    target_date = date(2026, 10, 28)
    slots = [
        SlotInfo(target_date, time(9, 0), time(9, 30)),
        SlotInfo(target_date, time(9, 30), time(10, 0)),
        SlotInfo(target_date, time(10, 30), time(11, 0)),
        SlotInfo(target_date, time(11, 0), time(11, 30)),
        SlotInfo(target_date, time(14, 0), time(14, 30)),
        SlotInfo(target_date, time(17, 0), time(17, 30)),
    ]
    return FakeBookingGateway(available_slots={target_date: slots})
