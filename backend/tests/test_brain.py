from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.brain.engine import Engine
from app.brain.language import extract, recognize
from app.schemas import Intent, SessionView, State

NOW = datetime(2026, 10, 26, 9, tzinfo=ZoneInfo("Asia/Karachi"))


@pytest.mark.parametrize("text,intent", [
    ("Book a haircut", Intent.CREATE), ("How do I cancel a booking?", Intent.INFO),
    ("Don't cancel my booking", Intent.DENY), ("cancel my appointment", Intent.CANCEL),
    ("reschedule my booking", Intent.RESCHEDULE), ("Is Friday available?", Intent.AVAILABILITY),
    ("yes please", Intent.CONFIRM), ("yes but make it Friday", Intent.MODIFY),
    ("cancel my appointment and book another", Intent.UNKNOWN), ("read a book", Intent.UNKNOWN),
    ("What are your prices?", Intent.INFO), ("repeat that", Intent.REPEAT),
    ("What's the weather?", Intent.UNKNOWN), ("goodbye", Intent.END),
])
def test_intent_rules(text, intent):
    assert recognize(text).intent == intent


@pytest.mark.parametrize("text,expected", [
    ("tomorrow at 5 PM", {"date": "2026-10-27", "time": "17:00"}),
    ("next Monday at 17:30", {"date": "2026-11-02", "time": "17:30"}),
    ("Friday afternoon", {"date": "2026-10-30", "period": "afternoon"}),
    ("five thirty PM", {"time": "17:30"}),
    ("half past four PM", {"time": "16:30"}),
    ("change that to six PM", {"time": "18:00"}),
    ("Actually make it tomorrow", {"date": "2026-10-27"}),
    ("No, I meant Friday", {"date": "2026-10-30"}),
    ("haircut and beard", {"service": "combo"}),
    ("NL-ABC12345", {"reference": "NL-ABC12345"}),
])
def test_entities(text, expected):
    result = extract(text, NOW)
    assert not result.issues
    for key, value in expected.items():
        assert getattr(result.entities, key) == value


@pytest.mark.parametrize("text,field", [
    ("at 5", "time"), ("five thirty", "time"), ("half past four", "time"),
    ("at 25:00", "time"), ("at 5:99 PM", "time"),
    ("tomorrow Friday", "date"), ("2026-02-30", "date"),
    ("11/12/2026", "date"), ("at 3 PM or 5 PM", "time"),
    ("next week", "date"), ("book a massage", "service"),
    ("haircut or beard trim", "service"),
])
def test_ambiguous_or_invalid_values_are_cleared(text, field):
    result = extract(text, NOW)
    assert field in result.issues
    assert getattr(result.entities, field) is None


class NoWrites:
    def __init__(self):
        self.checks = 0

    def check(self, entities, excluding=None):
        self.checks += 1

    def day(self, value):
        return datetime.fromisoformat(value).date()

    def create(self, entities):
        raise AssertionError("No write may occur before explicit confirmation")


def test_real_state_machine_missing_details_corrections_and_recovery():
    store = NoWrites()
    engine = Engine(store, NOW)
    c = engine.turn(SessionView(id="test"), "Book a haircut tomorrow at 3 PM")
    assert c.state == State.COLLECTING
    assert c.missing_information == ["name"]
    c = engine.turn(c, "Actually make it 5 PM instead")
    assert c.entities.time == "17:00"
    assert c.entities.date == "2026-10-27"
    assert c.entities.service == "haircut"
    assert c.entities.name is None
    assert store.checks == 2
    c = engine.turn(c, "Alex Example")
    assert c.state == State.CONFIRMING
    c = engine.turn(c, "No, I meant Friday")
    assert c.entities.date == "2026-10-30"
    assert c.entities.name == "Alex Example"
    assert c.state == State.CONFIRMING
    c = engine.turn(c, "what is the weather")
    assert c.last_decision.matched_rule == "fallback.context_unknown"
    assert c.entities.name == "Alex Example"
    c = engine.turn(c, "no")
    assert c.state == State.IDLE
    assert c.proposed_action is None


def test_ambiguity_invalidates_old_time_and_confirmation():
    engine = Engine(NoWrites(), NOW)
    c = engine.turn(SessionView(id="test"), "Book a haircut tomorrow at 3 PM")
    c = engine.turn(c, "Alex Example")
    c = engine.turn(c, "Actually make it five thirty")
    assert c.entities.time is None
    assert c.proposed_action is None
    c = engine.turn(c, "yes")
    assert c.last_decision.matched_rule == "confirmation.no_proposal"


def test_info_and_repeat_preserve_context_and_restart_clears_it():
    engine = Engine(NoWrites(), NOW)
    c = engine.turn(SessionView(id="test"), "Book a haircut tomorrow")
    before = c.entities.model_dump()
    c = engine.turn(c, "what are your hours")
    assert c.entities.model_dump() == before
    previous_reply = c.reply
    c = engine.turn(c, "repeat")
    assert c.reply == previous_reply
    c = engine.turn(c, "start over")
    assert c.entities.service is None
    assert c.state == State.IDLE


def test_unparsed_correction_and_period_change_invalidate_confirmation():
    engine = Engine(NoWrites(), NOW)
    c = engine.turn(SessionView(id="test"), "book a haircut tomorrow at 5 PM")
    c = engine.turn(c, "Alex Example")
    c = engine.turn(c, "Actually, change the details")
    assert c.proposed_action is None
    c = engine.turn(c, "yes")
    assert c.last_decision.matched_rule == "confirmation.no_proposal"
    c = engine.turn(c, "Friday afternoon")
    assert c.entities.time is None
    assert c.entities.period == "afternoon"
    assert c.entities.name == "Alex Example"
    assert c.missing_information == ["time"]


def test_negated_command_with_entities_discards_proposal():
    engine = Engine(NoWrites(), NOW)
    c = engine.turn(SessionView(id="test"), "book a haircut tomorrow at 5 PM")
    c = engine.turn(c, "Alex Example")
    c = engine.turn(c, "don't book a haircut tomorrow")
    assert c.state == State.IDLE
    assert c.proposed_action is None


@pytest.mark.parametrize("text", ["I don't know", "tell me a joke", "order some food", "what is my name", "maybe later"])
def test_uncertainty_or_requests_are_not_customer_names(text):
    result = extract(text, NOW, expecting_name=True)
    assert result.entities.name is None
