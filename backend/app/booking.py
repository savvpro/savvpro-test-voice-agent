from __future__ import annotations

from datetime import datetime, timedelta
from threading import RLock

from app.conversation.models import ServiceSpec

SERVICES = {
    "oil_change": ServiceSpec("oil_change", "oil change", 30, "general"),
    "tire_rotation": ServiceSpec("tire_rotation", "tire rotation", 60, "lift"),
    "brake_inspection": ServiceSpec("brake_inspection", "brake inspection", 90, "lift"),
    "battery_check": ServiceSpec("battery_check", "battery check", 30, "electrical"),
    "general_diagnostic": ServiceSpec("general_diagnostic", "general diagnostic", 60, "diagnostic"),
}

CAPACITY = {"general": 2, "lift": 1, "electrical": 1, "diagnostic": 1}


class BookingStore:
    """Ephemeral store. Guarantees atomic booking only inside this process."""

    def __init__(self) -> None:
        self.lock = RLock()
        self.bookings: list[dict] = []

    def is_available(self, start: datetime, service_key: str) -> bool:
        spec = SERVICES[service_key]
        end = start + timedelta(minutes=spec.duration_minutes)
        overlaps = 0
        for booking in self.bookings:
            booked_spec = SERVICES[booking["service"]]
            if booked_spec.resource != spec.resource:
                continue
            booked_start = datetime.fromisoformat(booking["slot"])
            booked_end = booked_start + timedelta(minutes=booked_spec.duration_minutes)
            if start < booked_end and booked_start < end:
                overlaps += 1
        return overlaps < CAPACITY[spec.resource]

    def alternatives(self, requested: datetime, service_key: str) -> list[datetime]:
        candidates: list[datetime] = []
        for day_delta in range(0, 7):
            day = (requested + timedelta(days=day_delta)).date()
            for hour in range(8, 17):
                for minute in (0, 30):
                    slot = requested.replace(
                        year=day.year,
                        month=day.month,
                        day=day.day,
                        hour=hour,
                        minute=minute,
                        second=0,
                        microsecond=0,
                    )
                    if slot >= requested and self.is_available(slot, service_key):
                        candidates.append(slot)
        requested_part = "morning" if requested.hour < 12 else "afternoon"
        candidates.sort(
            key=lambda slot: (
                slot.date() != requested.date(),
                ("morning" if slot.hour < 12 else "afternoon") != requested_part,
                abs((slot - requested).total_seconds()),
                slot,
            )
        )
        return candidates[:3]

    def confirm(self, draft: dict, confirmation_number: str) -> dict | None:
        start = datetime.fromisoformat(draft["slot"])
        with self.lock:
            if not self.is_available(start, draft["service"]):
                return None
            booking = {**draft, "confirmation_number": confirmation_number}
            self.bookings.append(booking)
            return booking
