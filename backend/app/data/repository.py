"""In-memory implementations of the data-access interfaces.

Thread safety
-------------
* ``InMemoryParcelRepository`` uses a single ``threading.Lock`` that
  protects every mutation (booking, releasing, cancelling, phone failures).
  All compound operations (e.g. rebook = release + book) are performed
  inside one ``with self._lock:`` block so they are atomic.

* ``InMemorySessionStore`` has a store-level lock for create/delete and
  each ``Session`` carries its own lock for per-session turn serialisation.
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, date, datetime

from app.core.logging import get_logger
from app.data.interfaces import IParcelRepository, ISessionStore
from app.models.parcel import (
    DeliverySlot,
    Parcel,
    ParcelStatus,
    PickupPoint,
)
from app.models.session import DialogueState, Session

log = get_logger(__name__)


# ── Parcel repository ─────────────────────────────────────────────────

class InMemoryParcelRepository(IParcelRepository):
    """In-memory store for parcels, delivery slots, and pickup points.

    Args:
        parcels: Pre-loaded list of parcels.
        slots: Pre-generated slot grid (7 days × 3 periods).
        pickup_points: Pre-loaded list of pickup points.
        max_phone_attempts: Lock a parcel after this many failures.
    """

    def __init__(
        self,
        parcels: list[Parcel],
        slots: list[DeliverySlot],
        pickup_points: list[PickupPoint],
        max_phone_attempts: int = 3,
    ) -> None:
        self._lock = threading.Lock()
        self._max_phone_attempts = max_phone_attempts

        # Index by primary key for O(1) lookup.
        self._parcels: dict[str, Parcel] = {p.tracking_id: p for p in parcels}
        self._slots: dict[str, DeliverySlot] = {s.slot_id: s for s in slots}
        self._pickup_points: dict[str, PickupPoint] = {
            pp.point_id: pp for pp in pickup_points
        }

    # -- Parcels --------------------------------------------------------

    def get_parcel(self, tracking_id: str) -> Parcel | None:
        return self._parcels.get(tracking_id)

    # -- Slots ----------------------------------------------------------

    def list_slots(self, start: date, end: date) -> list[DeliverySlot]:
        return [
            s for s in self._slots.values()
            if start <= s.date <= end
        ]

    def get_slot(self, slot_id: str) -> DeliverySlot | None:
        return self._slots.get(slot_id)

    def book_slot(self, slot_id: str, tracking_id: str) -> bool:
        """Atomically book one place in *slot_id* for *tracking_id*.

        Sets ``parcel.current_slot_id`` to the new slot.
        Returns False if the slot is full or not found.
        """
        with self._lock:
            slot = self._slots.get(slot_id)
            if slot is None or slot.is_full:
                return False
            parcel = self._parcels.get(tracking_id)
            if parcel is None:
                return False
            slot.booked += 1
            parcel.current_slot_id = slot_id
            return True

    def release_slot(self, slot_id: str, tracking_id: str) -> bool:
        """Atomically release one booking from *slot_id*.

        Clears ``parcel.current_slot_id`` if it matched.
        Returns False if nothing to release.
        """
        with self._lock:
            return self._release_slot_unlocked(slot_id, tracking_id)

    def _release_slot_unlocked(self, slot_id: str, tracking_id: str) -> bool:
        """Release without acquiring the lock (caller holds it)."""
        slot = self._slots.get(slot_id)
        if slot is None or slot.booked <= 0:
            return False
        parcel = self._parcels.get(tracking_id)
        if parcel is None:
            return False
        if parcel.current_slot_id != slot_id:
            return False
        slot.booked -= 1
        parcel.current_slot_id = None
        return True

    def rebook_slot(
        self,
        old_slot_id: str,
        new_slot_id: str,
        tracking_id: str,
    ) -> bool:
        """Atomically release *old_slot_id* and book *new_slot_id*.

        If the new slot is full the old slot remains unchanged and the
        method returns False.
        """
        with self._lock:
            new_slot = self._slots.get(new_slot_id)
            if new_slot is None or new_slot.is_full:
                return False
            parcel = self._parcels.get(tracking_id)
            if parcel is None:
                return False
            # Release old (if any).
            if old_slot_id and parcel.current_slot_id == old_slot_id:
                old_slot = self._slots.get(old_slot_id)
                if old_slot is not None and old_slot.booked > 0:
                    old_slot.booked -= 1
            # Book new.
            new_slot.booked += 1
            parcel.current_slot_id = new_slot_id
            return True

    # -- Pickup points --------------------------------------------------

    def list_pickup_points(
        self, open_on: date | None = None
    ) -> list[PickupPoint]:
        points = list(self._pickup_points.values())
        if open_on is not None:
            points = [pp for pp in points if pp.is_open_on(open_on)]
        return points

    def get_pickup_point(self, point_id: str) -> PickupPoint | None:
        return self._pickup_points.get(point_id)

    # -- Parcel lifecycle -----------------------------------------------

    def cancel_parcel(self, tracking_id: str) -> bool:
        with self._lock:
            parcel = self._parcels.get(tracking_id)
            if parcel is None:
                return False
            if parcel.status == ParcelStatus.CANCELLED:
                return False
            # Release slot if one is booked.
            if parcel.current_slot_id:
                self._release_slot_unlocked(
                    parcel.current_slot_id, tracking_id
                )
            parcel.status = ParcelStatus.CANCELLED
            return True

    # -- Phone verification tracking ------------------------------------

    def increment_phone_failures(self, tracking_id: str) -> int:
        with self._lock:
            parcel = self._parcels.get(tracking_id)
            if parcel is None:
                return 0
            parcel.phone_failures += 1
            if parcel.phone_failures >= self._max_phone_attempts:
                parcel.locked = True
            return parcel.phone_failures

    def is_parcel_locked(self, tracking_id: str) -> bool:
        parcel = self._parcels.get(tracking_id)
        if parcel is None:
            return False
        return parcel.locked


# ── Session store ─────────────────────────────────────────────────────

class InMemorySessionStore(ISessionStore):
    """Dict-backed session store with per-session locking."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}

    def create_session(self) -> Session:
        session = Session(
            session_id=str(uuid.uuid4()),
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def save_session(self, session: Session) -> None:
        with self._lock:
            self._sessions[session.session_id] = session

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.ended = True
                session.state = DialogueState.END
