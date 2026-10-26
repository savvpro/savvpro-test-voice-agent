"""Simple in-memory sliding-window rate limiter (single-process, free)."""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from typing import Deque, DefaultDict


class SlidingWindowRateLimiter:
    """Allow `limit` hits per `window_seconds` for each key (IP or session)."""

    def __init__(self, limit: int = 60, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: DefaultDict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            q = self._hits[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# Disabled automatically under pytest; override with RATE_LIMIT_ENABLED=1/0
def rate_limit_enabled() -> bool:
    flag = os.environ.get("RATE_LIMIT_ENABLED", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    # Auto-off in tests
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return True


turn_limiter = SlidingWindowRateLimiter(
    limit=_env_int("RATE_LIMIT_TURN", 60),
    window_seconds=float(_env_int("RATE_LIMIT_WINDOW_SEC", 60)),
)
