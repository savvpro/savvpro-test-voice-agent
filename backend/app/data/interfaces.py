"""Abstract interfaces for data access.

Concrete implementations live in ``repository.py``.  Keeping the interfaces
separate allows swapping the in-memory stores for database-backed ones
without touching the brain or API layers.
"""

from __future__ import annotations

import abc
from datetime import date

from app.models.parcel import DeliverySlot, Parcel, PickupPoint
from app.models.session import Session

# ── Parcel repository ─────────────────────────────────────────────────

class IParcelRepository(abc.ABC):
    """Read and mutate parcel, slot, and pickup-point data."""

    # -- Parcels --------------------------------------------------------

    @abc.abstractmethod
    def get_parcel(self, tracking_id: str) -> Parcel | None:
        """Return the parcel or ``None`` if not found."""

    # -- Slots ----------------------------------------------------------

    @abc.abstractmethod
    def list_slots(self, start: date, end: date) -> list[DeliverySlot]:
        """Return slots whose date is in ``[start, end]`` inclusive."""

    @abc.abstractmethod
    def get_slot(self, slot_id: str) -> DeliverySlot | None:
        """Return a single slot by ID or ``None``."""

    @abc.abstractmethod
    def book_slot(self, slot_id: str, tracking_id: str) -> bool:
        """Atomically book a slot.  Returns False if the slot is full."""

    @abc.abstractmethod
    def release_slot(self, slot_id: str, tracking_id: str) -> bool:
        """Atomically release one booking from a slot.

        Returns False if the slot was not booked or the parcel had no
        current slot.
        """

    @abc.abstractmethod
    def rebook_slot(
        self,
        old_slot_id: str,
        new_slot_id: str,
        tracking_id: str,
    ) -> bool:
        """Atomically release *old_slot_id* and book *new_slot_id*.

        Returns False if the new slot is full (old slot unchanged).
        """

    # -- Pickup points --------------------------------------------------

    @abc.abstractmethod
    def list_pickup_points(
        self, open_on: date | None = None
    ) -> list[PickupPoint]:
        """Return all pickup points, optionally filtered to those open on
        *open_on*.
        """

    @abc.abstractmethod
    def get_pickup_point(self, point_id: str) -> PickupPoint | None:
        """Return a single pickup point by ID or ``None``."""

    # -- Parcel lifecycle -----------------------------------------------

    @abc.abstractmethod
    def cancel_parcel(self, tracking_id: str) -> bool:
        """Cancel a parcel and release its current slot.

        Returns False if the parcel was not found or already cancelled.
        """

    # -- Phone verification tracking ------------------------------------

    @abc.abstractmethod
    def increment_phone_failures(self, tracking_id: str) -> int:
        """Increment the phone-failure counter for a parcel.

        Returns the *new* failure count.  If the count reaches the
        configured maximum the parcel is automatically locked.
        """

    @abc.abstractmethod
    def is_parcel_locked(self, tracking_id: str) -> bool:
        """Return True if the parcel has been locked due to too many
        verification failures.
        """


# ── Session store ─────────────────────────────────────────────────────

class ISessionStore(abc.ABC):
    """Create, read, update, and delete caller sessions."""

    @abc.abstractmethod
    def create_session(self) -> Session:
        """Create a new session and return it."""

    @abc.abstractmethod
    def get_session(self, session_id: str) -> Session | None:
        """Return the session or ``None`` if not found."""

    @abc.abstractmethod
    def save_session(self, session: Session) -> None:
        """Persist updates to an existing session."""

    @abc.abstractmethod
    def delete_session(self, session_id: str) -> None:
        """Mark a session as ended and remove it from the active store."""
