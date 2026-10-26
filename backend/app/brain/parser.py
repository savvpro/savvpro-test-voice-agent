from datetime import date

from app.brain.extractors import (
    detect_choice,
    detect_date,
    detect_name,
    detect_phone,
    detect_relation,
    detect_time,
)
from app.brain.nlu import NLUResult, detect_intents, detect_service


def parse(text: str, today: date, expecting: str | None = None) -> NLUResult:

    return NLUResult(
        intents=detect_intents(text),
        service=detect_service(text),
        appt_date=detect_date(text, today),
        appt_time=detect_time(text, expecting),
        name=detect_name(text, expecting),
        phone=detect_phone(text),
        choice=detect_choice(text),
        relation=detect_relation(text),
    )
