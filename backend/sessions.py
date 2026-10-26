"""
In-memory session store keyed by session_id.

In a real product this would be Redis or a database. For the assessment
demo, an in-process dict is enough to demonstrate the architecture.
"""

from __future__ import annotations

import threading
import uuid
from typing import Dict, Optional

from .brain import Session


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, Session] = {}

    def new(self) -> Session:
        sid = uuid.uuid4().hex[:12]
        s = Session(session_id=sid)
        with self._lock:
            self._sessions[sid] = s
        return s

    def get(self, sid: str) -> Optional[Session]:
        with self._lock:
            return self._sessions.get(sid)

    def get_or_create(self, sid: Optional[str]) -> Session:
        if sid:
            existing = self.get(sid)
            if existing:
                return existing
        return self.new()

    def reset(self, sid: str) -> Session:
        with self._lock:
            self._sessions.pop(sid, None)
        return self.new()

    def all_(self) -> dict:
        with self._lock:
            return dict(self._sessions)


SESSIONS = SessionStore()
