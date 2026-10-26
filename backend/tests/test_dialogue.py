import sqlite3
from dataclasses import asdict
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


def test_decision_fields(conn: sqlite3.Connection) -> None:
    [(_, d)] = talk(conn, "book with Dr Patel")
    assert asdict(d) == {
        "intent": "book",
        "entities": {"doctor_id": "patel"},
        "state": "collecting",
        "action": "ask_name",
        "slots": {"doctor_id": "patel"},
    }


# ---------- fix round 1: read-back safety and multi-turn corrections ----------

BASE = ("book an appointment", "sara lee", "march 4 1990", "dr patel", "tomorrow", "2pm")


def test_negated_please_never_books_or_cancels(conn: sqlite3.Connection) -> None:
    before = count(conn)
    turns = talk(conn, *BASE, "no please don't book it")
    assert turns[-1][1].action == "ask_what_to_change"
    assert count(conn) == before
    turns = talk(conn, "cancel my appointment", "CLN-JC01", "no please don't cancel it")
    assert turns[-1][1].action == "ask_intent"
    assert find_upcoming(conn, NOW, ref="CLN-JC01") != []


def test_yes_with_correction_rereads(conn: sqlite3.Connection) -> None:
    before = count(conn)
    turns = talk(conn, *BASE, "okay but can you make it 3:30 instead")
    assert turns[-1][1].action == "confirm_booking" and "3:30 PM" in turns[-1][0]
    assert count(conn) == before
    turns = talk(conn, "reschedule", "CLN-JC01", "friday at 10am", "sure but please make it 11")
    assert turns[-1][1].action == "ask_what_to_change"
    assert find_upcoming(conn, NOW, ref="CLN-JC01")[0].start == datetime(2026, 10, 27, 10)
    turns = talk(conn, "reschedule", "CLN-JC01", "friday at 10am", "sure but make it 11", "11")
    assert turns[-1][1].action == "confirm_reschedule" and "11:00 AM" in turns[-1][0]


def test_no_with_correction_rereads(conn: sqlite3.Connection) -> None:
    turns = talk(conn, *BASE, "no make it 3:30")
    assert turns[-1][1].action == "confirm_booking" and "3:30 PM" in turns[-1][0]


def test_new_day_while_offering(conn: sqlite3.Connection) -> None:
    taken = ("book with dr khan tomorrow at 3pm", "alex kim", "jan 2 1980")
    turns = talk(conn, *taken, "do you have anything on friday")
    assert turns[-1][1].action == "ask_time" and "Friday, October 30" in turns[-1][0]
    turns = talk(conn, *taken, "friday at 10am")
    assert turns[-1][1].action == "confirm_booking"
    assert "Friday, October 30 at 10:00 AM" in turns[-1][0]


def test_time_while_choosing_only_picks(conn: sqlite3.Connection) -> None:
    state, turns = run(conn, "reschedule", "emily stone", "february 29 1992", "the 2 pm one")
    assert turns[-1][1].action == "ask_date"
    assert state.slots["ref"] == "CLN-ES01" and "time" not in state.slots
    turns = talk(conn, "reschedule", "emily stone", "february 29 1992", "the 2 pm one", "friday")
    assert turns[-1][1].action == "ask_time"
    turns = talk(conn, "cancel", "emily stone", "february 29 1992", "the tuesday one")
    assert turns[-1][1].action == "confirm_cancel" and "CLN-ES01" in turns[-1][0]


def test_reschedule_keeps_doctor(conn: sqlite3.Connection) -> None:
    state, turns = run(conn, "reschedule", "CLN-ES01", "friday at 10am", "no", "the doctor")
    assert state.slots["doctor_id"] == "nguyen"
    assert "Patel" not in turns[-1][0]
    state, _ = run(conn, "reschedule", "CLN-ES01", "friday at 10am with dr patel")
    assert state.slots["doctor_id"] == "nguyen"


def test_date_at_cancel_confirm_reconfirms(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "cancel", "CLN-JC01", "is that the one on tuesday")
    assert turns[-1][1].action == "confirm_cancel"


def test_no_progress_turns_give_up(conn: sqlite3.Connection) -> None:
    same = "john carter july 12 1985"
    state, turns = run(conn, "cancel", same, same, same, same)
    assert [d.action for _, d in turns[1:]] == ["ask_name", "reprompt", "reprompt", "give_up"]
    assert state.ended
    turns = talk(conn, "cancel", same, "john carter")
    assert turns[-1][1].action == "confirm_cancel"
    state, turns = run(conn, "book", "sara lee", "march 4 1990", "dr smith", "dr smith", "dr smith")
    assert [d.action for _, d in turns[-3:]] == ["unknown_doctor", "unknown_doctor", "give_up"]


def test_switch_cancel_to_reschedule_keeps_ref(conn: sqlite3.Connection) -> None:
    state, turns = run(conn, "cancel", "CLN-JC01", "actually i want to reschedule it")
    assert state.flow == "reschedule" and state.slots["ref"] == "CLN-JC01"
    assert turns[-1][1].action == "ask_date"


def test_filler_is_not_a_name(conn: sqlite3.Connection) -> None:
    for filler in ("uh", "uhh", "umm", "hmm", "er"):
        state, turns = run(conn, "book", filler)
        assert turns[-1][1].action == "reprompt" and "name" not in state.slots


def test_reprompt_does_not_use_up_lookup_retry(conn: sqlite3.Connection) -> None:
    state, turns = run(conn, "cancel", "...", "CLN-ZZZZ")
    assert turns[-1][1].action == "not_found"
    assert state.flow == "cancel" and state.step == "lookup"  # still the retry, not the offer


def test_help_with_a_request_books(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "can you help me book with dr patel tomorrow at 2pm")
    assert turns[-1][1].action == "ask_name"


def test_specialty_change_time_uses_any_gp(conn: sqlite3.Connection) -> None:
    turns = talk(
        conn, "book", "sara lee", "march 4 1990", "any doctor", "tomorrow at 10am", "make it 3pm"
    )
    assert "Dr. Omar Khan" in turns[-2][0]
    assert turns[-1][1].action == "confirm_booking" and "Dr. Anita Patel" in turns[-1][0]


# ---------- fix round 2: agreeing details at read-back are not corrections ----------

KHAN = ("book with dr khan tomorrow at 11am my name is sara lee", "march 4 1990")


def test_yes_with_agreeing_detail_books(conn: sqlite3.Connection) -> None:
    turns = talk(conn, *KHAN, "yes it's just for a checkup")
    assert turns[-1][1].action == "booked"
    [a] = find_upcoming(conn, NOW, name="Sara Lee", dob=datetime(1990, 3, 4).date())
    assert (a.doctor_id, a.start) == ("khan", datetime(2026, 10, 27, 11))
    turns = talk(conn, "book with dr khan tomorrow at 10am my name is tom hill", "june 5 1970",
                 "yes, morning is great")  # fmt: skip
    assert turns[-1][1].action == "booked"
    [a] = find_upcoming(conn, NOW, name="Tom Hill", dob=datetime(1970, 6, 5).date())
    assert a.start == datetime(2026, 10, 27, 10)
    turns = talk(conn, "book with dr patel tomorrow at 2pm my name is sam lee", "march 4 1990",
                 "yes the afternoon works")  # fmt: skip
    assert turns[-1][1].action == "booked"


def test_conflicting_detail_is_a_correction(conn: sqlite3.Connection) -> None:
    turns = talk(conn, *KHAN, "yes but in the afternoon")
    assert turns[-1][1].action == "offer_slots"
    turns = talk(conn, *KHAN, "yes it's for a skin rash")
    assert turns[-1][1].action == "confirm_booking" and "Dr. Linh Nguyen" in turns[-1][0]


def test_agreeing_specialty_keeps_doctor_while_collecting(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "book", "sara lee", "march 4 1990", "dr khan", "it's for a general checkup",
                 "tomorrow at 11am")  # fmt: skip
    assert "Dr. Omar Khan" in turns[-1][0]


def test_actually_is_not_a_correction(conn: sqlite3.Connection) -> None:
    turns = talk(conn, *BASE, "yes that's actually perfect")
    assert turns[-1][1].action == "booked"


def test_misses_reset_after_found(conn: sqlite3.Connection) -> None:
    state, turns = run(conn, "cancel", "CLN-ZZZZ", "CLN-JC01")
    assert turns[-1][1].action == "confirm_cancel" and state.misses == 0


def test_repeating_taken_slot_while_offering_explains(conn: sqlite3.Connection) -> None:
    taken = ("book with dr khan tomorrow at 3pm", "alex kim", "jan 2 1980", "tomorrow at 3pm")
    state, turns = run(conn, *taken)
    assert turns[-1][1].action == "offer_slots" and "taken" in turns[-1][0]
    assert state.failures == 0


# ---------- final review: hedged yes never executes; evening ----------


def test_hedged_yes_at_cancel_never_cancels(conn: sqlite3.Connection) -> None:
    for hedge in ("yes but keep it", "yes, wait", "yes actually", "yes hold on"):
        turns = talk(conn, "cancel", "CLN-JC01", hedge)
        assert turns[-1][1].action == "reprompt" and "Shall I cancel it?" in turns[-1][0]
        assert find_upcoming(conn, NOW, ref="CLN-JC01") != []
    turns = talk(conn, "cancel", "CLN-JC01", "yes but keep it", "yes")
    assert turns[-1][1].action == "cancelled"


def test_yes_actually_wait_hold_on_do_not_book(conn: sqlite3.Connection) -> None:
    before = count(conn)
    for hedge in ("yes actually", "yes, wait", "yeah hold on"):
        turns = talk(conn, *BASE, hedge)
        assert turns[-1][1].action == "ask_what_to_change"
    assert count(conn) == before


def test_evening_conflicts_with_earlier_readback(conn: sqlite3.Connection) -> None:
    before = count(conn)
    for base in (KHAN, BASE):  # 11 AM and 2 PM read-backs
        state, turns = run(conn, *base, "yes, in the evening")
        assert turns[-1][1].action == "offer_slots"
        assert all(t[11:] >= "16:00" for _, t in state.offers[:1])
    assert count(conn) == before
    turns = talk(conn, "book with dr patel tomorrow at 4pm my name is sam lee", "march 4 1990",
                 "yes, evening is good")  # fmt: skip
    assert turns[-1][1].action == "booked"


def test_future_dob_is_explained_not_just_reprompted(conn: sqlite3.Connection) -> None:
    turns = talk(conn, "book an appointment", "Sara Lee", "12 december 2026", "30-12-2026")
    for reply, d in turns[2:]:
        assert d.action == "future_dob"
        assert "future" in reply
        assert "Thanks." not in reply
    reply, d = talk(conn, "book an appointment", "Sara Lee", "12 december 1990")[-1]
    assert d.slots["dob"] == "1990-12-12"


def test_reprompt_drops_courtesy_lead(conn: sqlite3.Connection) -> None:
    reply, d = talk(conn, "book an appointment", "Sara Lee", "blah")[-1]
    assert d.action == "reprompt"
    assert reply == "Sorry, I didn't catch that. What's your date of birth?"
