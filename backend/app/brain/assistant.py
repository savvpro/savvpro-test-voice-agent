"""One call = one Assistant. It glues NLU and policy together; it holds no rules itself."""
from datetime import datetime
from typing import Callable

from app.brain.parser import parse
from app.brain.policy import handle_turn, start_call
from app.brain.state import EXPECTING, Session, TurnResult
from app.services.booking import ClinicCalendar


class Assistant:
    def __init__(self, calendar: ClinicCalendar, clock: Callable[[], datetime] = datetime.now):
        self.calendar = calendar
        self.clock = clock          # injected so tests can freeze "now"
        self.session = Session()

    def start(self) -> TurnResult:
        return start_call(self.session)

    def hear(self, text: str) -> TurnResult:
        now = self.clock()
        expecting = EXPECTING[self.session.state]
        nlu = parse(text, now.date(), expecting)
        return handle_turn(self.session, nlu, self.calendar, now)
