"""Pydantic models for booking data."""

from __future__ import annotations

from datetime import date, time
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class BookingStatus(str, Enum):
    """Lifecycle states of a booking."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Booking(BaseModel):
    """Represents a single restaurant reservation."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    guest_name: Optional[str] = None
    contact: Optional[str] = None
    date: Optional[date] = None
    time: Optional[time] = None
    party_size: Optional[int] = None
    status: BookingStatus = BookingStatus.PENDING

    def summary(self) -> str:
        """Return a human-readable summary of the booking."""
        parts = []
        if self.guest_name:
            parts.append(f"Name: {self.guest_name}")
        if self.date:
            parts.append(f"Date: {self.date.strftime('%A, %B %d, %Y')}")
        if self.time:
            parts.append(f"Time: {self.time.strftime('%I:%M %p')}")
        if self.party_size:
            parts.append(f"Party size: {self.party_size}")
        if self.contact:
            parts.append(f"Contact: {self.contact}")
        return " | ".join(parts) if parts else "No details yet"

    def is_complete(self) -> bool:
        """Check if all required fields are filled."""
        return all([
            self.guest_name,
            self.date,
            self.time,
            self.party_size is not None,
        ])
