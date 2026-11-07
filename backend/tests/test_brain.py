from datetime import date

from fastapi.testclient import TestClient

from app import nlu
from app.brain import Brain, Session
from app.main import app
from app.schedule import Schedule

TODAY = date(2026, 10, 26)  # a Monday; Tuesday 10:00 and 10:30 are pre-booked


def call():
    b, s = Brain(Schedule(TODAY), TODAY), Session()
    b.greet(s)
    return b, s


def test_nlu_times():
    assert nlu.parse_time("half past three") == ("ok", "15:30")
    assert nlu.parse_time("at 5") == ("ambiguous", (5, 0))
    assert nlu.parse_time("3 pm") == ("ok", "15:00")
    assert nlu.parse_time("evening", pending=(6, 0)) == ("ok", "18:00")
    assert nlu.parse_time("the 28th") is None


def test_nlu_dates():
    assert nlu.parse_date("tomorrow", TODAY) == "2026-10-27"
    assert nlu.parse_date("next friday", TODAY) == "2026-10-30"
    assert nlu.parse_date("the 28th", TODAY) == "2026-10-28"


def test_book_in_one_utterance_then_confirm():
    b, s = call()
    t = b.handle(s, "Hi, I'd like to book an appointment tomorrow at 2 pm, my name is Ali")
    assert t.state == "CONFIRM" and t.slots["time"] == "14:00"
    t = b.handle(s, "yes")
    assert t.done and "APT-" in t.reply


def test_missing_slots_are_asked_one_by_one():
    b, s = call()
    assert b.handle(s, "I need an appointment").state == "ASK_NAME"
    assert b.handle(s, "Sara Khan").state == "ASK_DATE"
    assert b.handle(s, "friday").state == "ASK_TIME"
    assert b.handle(s, "at 11").state == "CONFIRM"


def test_taken_slot_offers_alternatives():
    b, s = call()
    t = b.handle(s, "book tomorrow at 10 am, I'm Ali")
    assert "already booked" in t.reply and "9:30 AM" in t.reply and "time" not in t.slots


def test_ambiguous_time_then_outside_hours():
    b, s = call()
    t = b.handle(s, "book tomorrow at 6, my name is Ali")
    assert "morning or in the evening" in t.reply
    t = b.handle(s, "evening")
    assert t.state == "ASK_TIME" and "9 AM and 5 PM" in t.reply


def test_correction_at_confirmation():
    b, s = call()
    b.handle(s, "book tomorrow at 2 pm, name is Ali")
    t = b.handle(s, "no, make it thursday")
    assert t.state == "CONFIRM" and t.slots["date"] == "2026-10-29"
    assert any("correction date" in x for x in t.trace)


def test_weekend_and_past_rejected():
    b, s = call()
    t = b.handle(s, "book saturday at 10 am, name is Ali")
    assert "closed on weekends" in t.reply and "date" not in t.slots
    b, s = call()
    assert "already passed" in b.handle(s, "book on 2026-10-20 at 10 am, name is Ali").reply


def test_cancel_flow():
    b, s = call()
    t = b.handle(s, "cancel my appointment, my name is Sam Demo")
    assert t.state == "CONFIRM"
    assert b.handle(s, "yes").done and b.sched.find("Sam Demo") is None


def test_cancel_unknown_name():
    b, s = call()
    t = b.handle(s, "cancel my appointment, my name is Nobody Here")
    assert t.state == "ASK_NAME" and "couldn't find" in t.reply


def test_reschedule_flow():
    b, s = call()
    t = b.handle(s, "move my appointment to friday at 3 pm, my name is Sam Demo")
    assert t.state == "CONFIRM" and "from" in t.reply
    b.handle(s, "yes")
    assert b.sched.find("Sam Demo") == ("2026-10-30", "15:00")


def test_intent_switch_mid_flow():
    b, s = call()
    b.handle(s, "book tomorrow at 2 pm")
    t = b.handle(s, "actually cancel my appointment")
    assert t.intent == "cancel" and t.state == "ASK_NAME"


def test_repeat_human_and_silence():
    b, s = call()
    first = b.handle(s, "book an appointment").reply
    assert b.handle(s, "can you repeat that").reply == first
    assert b.handle(s, "let me talk to a human").done
    b, s = call()
    for _ in range(3):
        t = b.handle(s, "")
    assert t.done and "front desk" in t.reply


def test_api_roundtrip():
    c = TestClient(app)
    r = c.post("/sessions").json()
    t = c.post(f"/sessions/{r['session_id']}/turn", json={"text": "I want to book"}).json()
    assert t["state"] == "ASK_NAME" and t["trace"]
    assert c.post("/sessions/nope/turn", json={"text": "x"}).status_code == 404
