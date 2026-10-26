"""In-memory store: one Assistant per call. A real deployment would use Redis/a database."""
import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Callable

from app.brain.assistant import Assistant
from app.services.booking import ClinicCalendar
from app.services.seed import seed_calendar


class SessionStore:
    def __init__(self, clock: Callable[[], datetime], seed: bool = True, max_sessions: int = 500):
        self.clock = clock
        self.max_sessions = max_sessions
        self.calendar = ClinicCalendar()    
        if seed:
            seed_calendar(self.calendar, clock())
        self._sessions: "OrderedDict[str, Assistant]" = OrderedDict()

    def create(self) -> tuple[str, Assistant]:
        session_id = uuid.uuid4().hex
        bot = Assistant(self.calendar, clock=self.clock)
        self._sessions[session_id] = bot
        while len(self._sessions) > self.max_sessions:   # forget the oldest calls
            self._sessions.popitem(last=False)
        return session_id, bot

    def get(self, session_id: str) -> Assistant | None:
        return self._sessions.get(session_id)
