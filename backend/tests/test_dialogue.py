import sqlite3
from datetime import datetime

from app import dialogue
from app.dialogue import CallState, Decision
from app.scheduling import find_upcoming
from tests.conftest import NOW

BOOK_PATEL = ("book an appointment", "Sara Lee", "03/04/1990", "Dr Patel", "Friday")


def run(conn: sqlite3.Connection, *lines: str) -> tuple[CallState, list[tuple[str, Decision]]]:
    state, _, _ = dialogue.start_call()
    out = []
    for line in lines:
        state, reply, decision = dialogue.handle_turn(state, line, conn, NOW)
        out.append((reply, decision))
    return state, out


def talk(conn: sqlite3.Connection, *lines: str) -> list[tuple[str, Decision]]:
    return run(conn, *lines)[1]


def count(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute("SELECT count(*) FROM appointments WHERE status='booked'").fetchone()[0]
    )


def test_greeting() -> None:
    state, reply, d = dialogue.start_call()
    assert reply.startswith("Thanks for calling Maple Street Clinic.")
    assert d.action == "greet" and state.step == "greeting"


def test_happy_booking_one_sentence(conn: sqlite3.Connection) -> None:
    before = count(conn)
    turns = talk(
        conn,
        "Hi, I want to book with Dr Patel tomorrow at 2pm, my name is Sara Lee",
        "March 4 1990",
        "yes",
    )
    assert [d.action for _, d in turns] == ["ask_dob", "confirm_booking", "booked"]
    assert "Sara Lee, born March 4, 1990" in turns[1][0]
    assert "Tuesday, October 27 at 2:00 PM" in turns[1][0]
    reply = turns[-1][0]
    assert "CLN-" in reply
    ref = reply[reply.index("CLN-") : reply.index("CLN-") + 8]
    assert " ".join(ref.replace("-", "")) in reply
    assert count(conn) == before + 1


def test_step_by_step_booking(conn: sqlite3.Connection) -> None:
    turns = talk(
        conn, "book an appointment", "Sara Lee", "03/04/1990", "a skin check", "Friday", "10am"
    )
    actions = [d.action for _, d in turns]
    assert actions == [
        "ask_name",
        "ask_dob",
        "ask_doctor",
        "ask_date",
        "ask_time",
        "confirm_booking",
    ]
    assert "Dr. Linh Nguyen" in turns[-1][0]
    state, turns = run(
        conn,
        "book an appointment",
        "Sara Lee",
        "03/04/1990",
        "a skin check",
        "Friday",
        "10am",
        "yes",
    )
    assert turns[-1][1].action == "booked"
    appt = find_upcoming(conn, NOW, name="Sara Lee", dob=datetime(1990, 3, 4).date())
    assert [(a.doctor_id, a.start) for a in appt] == [("nguyen", datetime(2026, 10, 30, 10))]
    assert state.flow is None and state.step == "done"


def test_change_time_midway(conn: sqlite3.Connection) -> None:
    turns = talk(conn, *BOOK_PATEL, "2pm", "actually make it 3:30", "yes")
    assert turns[-3][1].action == "confirm_booking"
    assert turns[-2][1].action == "confirm_booking"
    assert "3:30 PM" in turns[-2][0]
    assert turns[-1][1].action == "booked"
    [a] = find_upcoming(conn, NOW, name="Sara Lee", dob=datetime(1990, 3, 4).date())
    assert a.start == datetime(2026, 10, 30, 15, 30)


def test_deny_at_readback(conn: sqlite3.Connection) -> None:
    turns = talk(conn, *BOOK_PATEL, "2pm", "no")
    assert turns[-1][1].action == "ask_what_to_change"
    turns = talk(conn, *BOOK_PATEL, "2pm", "no", "the time", "11am")
    assert turns[-2][1].action == "ask_time"
    assert turns[-1][1].action == "confirm_booking" and "11:00 AM" in turns[-1][0]


def test_slot_taken_offers_alternatives(conn: sqlite3.Connection) -> None:
    state, turns = run(conn, "book", "Sara Lee", "03/04/1990", "Dr Khan tomorrow at 3pm")
    assert turns[-1][1].action == "offer_slots"
    assert len(state.offers) == 3
    assert ["khan", "2026-10-27T15:00"] not in state.offers
    second = state.offers[1]
    state, turns = run(conn, "book", "Sara Lee", "03/04/1990", "Dr Khan tomorrow at 3pm",
                       "the second one", "yes")  # fmt: skip
    assert [d.action for _, d in turns[-2:]] == ["confirm_booking", "booked"]
    [a] = find_upcoming(conn, NOW, name="Sara Lee", dob=datetime(1990, 3, 4).date())
    assert [a.doctor_id, a.start.isoformat(timespec="minutes")] == second


def test_weekend_and_closed(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "book", "Sara Lee", "03/04/1990", "Dr Patel", "Saturday", "at 8pm")
    assert turns[-2][1].action == "explain_slot_problem"
    assert "weekend" in turns[-2][0].lower()
    assert turns[-1][1].action == "explain_slot_problem"
    assert "9" in turns[-1][0]


def test_unknown_doctor(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "book", "Sara Lee", "03/04/1990", "Dr Smith")
    assert turns[-1][1].action == "unknown_doctor"
    assert "Patel" in turns[-1][0]


def test_reprompt_then_give_up(conn: sqlite3.Connection) -> None:
    state, turns = run(conn, "blah", "blah", "blah")
    assert [d.action for _, d in turns] == ["reprompt", "reprompt", "give_up"]
    assert state.ended


def test_slot_fill_resets_failures(conn: sqlite3.Connection) -> None:
    state, turns = run(conn, "book", "...", "...", "Sara Lee", "...")
    assert turns[-1][1].action == "reprompt"
    assert state.failures == 1 and not state.ended


def test_repeat(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "book", "what?")
    assert turns[-1][1].action == "repeat"
    assert turns[-1][0] == turns[-2][0]


def test_help_reasks(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "book", "Sara Lee", "help")
    assert turns[-1][1].action == "help"
    assert "date of birth" in turns[-1][0]


def test_cancel_by_ref(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "cancel my appointment", "CLN-JC01", "yes")
    assert [d.action for _, d in turns] == ["ask_lookup", "confirm_cancel", "cancelled"]
    assert find_upcoming(conn, NOW, ref="CLN-JC01") == []


def test_cancel_multiple_matches(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "cancel", "Emily Stone", "February 29 1992")
    assert turns[-1][1].action == "choose_appointment"
    assert "1:" in turns[-1][0] and "2:" in turns[-1][0] and "3:" not in turns[-1][0]
    turns = talk(conn, "cancel", "Emily Stone", "February 29 1992", "the first one", "yes")
    assert [d.action for _, d in turns[-2:]] == ["confirm_cancel", "cancelled"]
    assert find_upcoming(conn, NOW, ref="CLN-ES01") == []
    assert find_upcoming(conn, NOW, ref="CLN-ES02") != []


def test_reschedule(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "reschedule", "CLN-JC01", "next Wednesday at 11", "yes")
    assert [d.action for _, d in turns] == [
        "ask_lookup",
        "ask_date",
        "confirm_reschedule",
        "rescheduled",
    ]
    [a] = find_upcoming(conn, NOW, ref="CLN-JC01")
    assert a.start == datetime(2026, 11, 4, 11) and a.doctor_id == "patel"


def test_not_found_then_offer_book(conn: sqlite3.Connection) -> None:
    state, turns = run(conn, "cancel", "CLN-ZZZZ", "CLN-YYYY")
    assert [d.action for _, d in turns[-2:]] == ["not_found", "not_found"]
    assert "book" in turns[-1][0].lower()
    state, turns = run(conn, "cancel", "CLN-ZZZZ", "CLN-YYYY", "yes")
    assert state.flow == "book" and turns[-1][1].action == "ask_name"


def test_switch_book_to_cancel(conn: sqlite3.Connection) -> None:
    state, turns = run(conn, "book", "actually I want to cancel")
    assert state.flow == "cancel"
    assert turns[-1][1].action == "ask_lookup"


def test_yes_with_flow_word_at_readback_confirms(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "reschedule", "CLN-JC01", "next Wednesday at 11", "yes cancel it")
    assert turns[-1][1].action == "rescheduled"


def test_emergency(conn: sqlite3.Connection) -> None:
    state, turns = run(conn, "book", "Sara Lee", "I'm having chest pain")
    assert turns[-1][1].action == "emergency"
    assert "911" in turns[-1][0]
    assert state.ended


def test_choice_by_number(conn: sqlite3.Connection) -> None:
    state, _ = run(conn, "book", "Sara Lee", "03/04/1990", "Dr Khan tomorrow at 3pm")
    third = state.offers[2]
    state, turns = run(conn, "book", "Sara Lee", "03/04/1990", "Dr Khan tomorrow at 3pm", "3")
    assert turns[-1][1].action == "confirm_booking"
    assert [state.slots["doctor_id"], f"{state.slots['date']}T{state.slots['time']}"] == third


def test_part_of_day_offers(conn: sqlite3.Connection) -> None:
    state, turns = run(conn, "book", "Sara Lee", "03/04/1990", "Dr Patel", "Friday morning")
    assert turns[-1][1].action == "offer_slots"
    assert state.offers[0] == ["patel", "2026-10-30T09:00"]


def test_empty_text(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "   ")
    assert turns[-1][1].action == "reprompt"
    turns = talk(conn, "")
    assert turns[-1][1].action == "reprompt"


def test_state_roundtrip(conn: sqlite3.Connection) -> None:
    state, _ = run(conn, "book", "Sara Lee", "03/04/1990", "Dr Khan tomorrow at 3pm")
    assert CallState.from_json(state.to_json()) == state
    assert state.offers


def test_decision_as_dict(conn: sqlite3.Connection) -> None:
    [(_, d)] = talk(conn, "book with Dr Patel")
    assert d.as_dict() == {
        "intent": "book",
        "entities": {"doctor_id": "patel"},
        "state": "collecting",
        "action": "ask_name",
        "slots": {"doctor_id": "patel"},
    }
