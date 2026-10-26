from brain.brain import handle_turn
from brain.state import Session


def test_out_of_scope_is_steered_back():
    session, reply, decision = handle_turn(Session(), "do you do dental?")
    assert "appointment" in reply.lower()
    assert decision["intent"] == "out_of_scope"


def test_greeting_enters_collection():
    session, reply, _ = handle_turn(Session(), "hello")
    assert session.current_state == "COLLECTING"
    assert "date" in reply.lower()
