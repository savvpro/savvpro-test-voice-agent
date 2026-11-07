"""Real-time system clock implementation of voice_agent.ports.Clock."""

from __future__ import annotations

from datetime import date, datetime, time

from voice_agent.ports import Clock


class SystemClock(Clock):
    """System clock delegating to local system date/time."""

    def today(self) -> date:
        return date.today()

    def now_time(self) -> time:
        return datetime.now().time()
