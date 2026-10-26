"""Live calls and the shared appointment book, kept in memory."""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Callable

from app.clinic.calendar import Calendar
from app.dialog.manager import Call


class CallStore:
    def __init__(self, max_calls: int = 200, clock: Callable[[], datetime] = datetime.now):
        self.clock = clock
        self.max_calls = max_calls
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.calendar = Calendar(self.clock().date())
        self.calls: OrderedDict[str, tuple[Call, list[dict]]] = OrderedDict()

    def start(self) -> tuple[str, Call, str]:
        call = Call(self.calendar, self.clock())
        greeting = call.greet()
        call_id = uuid.uuid4().hex[:12]
        self.calls[call_id] = (call, [])
        while len(self.calls) > self.max_calls:  # forget the oldest calls
            self.calls.popitem(last=False)
        return call_id, call, greeting

    def get(self, call_id: str) -> tuple[Call, list[dict]] | None:
        return self.calls.get(call_id)
