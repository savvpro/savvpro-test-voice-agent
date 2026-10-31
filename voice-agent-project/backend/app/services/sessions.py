"""In-memory session store with idle expiry (swap for Redis in production)."""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable

from ..brain.models import Session


class SessionStore:
    def __init__(self, ttl_seconds: int = 1800, timer: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._timer = timer
        self._lock = threading.Lock()
        self._items: dict[str, tuple[Session, float]] = {}

    def create(self) -> Session:
        session = Session(id=uuid.uuid4().hex)
        with self._lock:
            self._purge()
            self._items[session.id] = (session, self._timer())
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            self._purge()
            item = self._items.get(session_id)
            if item is None:
                return None
            self._items[session_id] = (item[0], self._timer())
            return item[0]

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._items.pop(session_id, None) is not None

    def _purge(self) -> None:
        now = self._timer()
        for key in [k for k, (_, seen) in self._items.items() if now - seen > self._ttl]:
            del self._items[key]
