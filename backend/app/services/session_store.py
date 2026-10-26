"""In-memory call sessions with an idle timeout.

Good enough for a single-process demo; a multi-worker deployment would move
this to Redis or the database.
"""

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.dialogue.frame import Frame

DEFAULT_TTL_SECONDS = 30 * 60


@dataclass
class HistoryEntry:
    role: Literal["caller", "agent"]
    text: str
    at: datetime


@dataclass
class CallSession:
    id: str
    frame: Frame
    seed: int
    history: list[HistoryEntry] = field(default_factory=list)
    ended: bool = False
    last_seen: float = 0.0
    # Turns of one call are handled one at a time, even if the client double-sends.
    lock: threading.Lock = field(default_factory=threading.Lock)


class SessionNotFoundError(KeyError):
    pass


class SessionStore:
    def __init__(
        self,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._sessions: dict[str, CallSession] = {}
        self._lock = threading.Lock()

    def create(self, seed: int | None = None) -> CallSession:
        session_id = uuid.uuid4().hex
        if seed is None:
            seed = uuid.UUID(session_id).int % 2**32
        session = CallSession(id=session_id, frame=Frame(), seed=seed, last_seen=self._clock())
        with self._lock:
            self._purge_expired()
            self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> CallSession:
        with self._lock:
            self._purge_expired()
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError(session_id)
            session.last_seen = self._clock()
            return session

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired()
            return len(self._sessions)

    def _purge_expired(self) -> None:
        cutoff = self._clock() - self.ttl_seconds
        for session_id in [k for k, s in self._sessions.items() if s.last_seen < cutoff]:
            del self._sessions[session_id]
