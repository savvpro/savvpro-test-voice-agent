"""In-memory SessionStore with TTL and max-size LRU eviction."""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from threading import Lock
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class SessionStore:
    """Thread-safe in-memory store for voice session state.

    Parameters
    ----------
    ttl_seconds:
        Seconds until an untouched session expires.
    max_size:
        Maximum number of sessions before the oldest is evicted (LRU).
    """

    def __init__(
        self,
        ttl_seconds: int = settings.session_ttl_seconds,
        max_size: int = settings.session_max_size,
    ) -> None:
        self._ttl = ttl_seconds
        self._max = max_size
        self._store: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._lock = Lock()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, (ts, _) in self._store.items() if now - ts > self._ttl]
        for k in expired:
            del self._store[k]
            logger.debug("session_expired", extra={"session_id": k})

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, session_id: str) -> dict[str, Any] | None:
        """Return session data or None if absent/expired."""
        with self._lock:
            self._evict_expired()
            if session_id not in self._store:
                return None
            ts, data = self._store[session_id]
            if time.monotonic() - ts > self._ttl:
                del self._store[session_id]
                return None
            # Touch (LRU)
            self._store.move_to_end(session_id)
            return data

    def set(self, session_id: str, data: dict[str, Any]) -> None:
        """Create or update a session, evicting LRU if at capacity."""
        with self._lock:
            self._evict_expired()
            if session_id in self._store:
                self._store.move_to_end(session_id)
            elif len(self._store) >= self._max:
                evicted, _ = self._store.popitem(last=False)
                logger.debug("session_evicted_lru", extra={"session_id": evicted})
            self._store[session_id] = (time.monotonic(), data)

    def delete(self, session_id: str) -> None:
        """Remove a session (no-op if not present)."""
        with self._lock:
            self._store.pop(session_id, None)

    def __len__(self) -> int:
        with self._lock:
            self._evict_expired()
            return len(self._store)

    def __contains__(self, session_id: str) -> bool:
        return self.get(session_id) is not None
