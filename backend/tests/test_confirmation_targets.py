"""A named confirmation cannot authorize a different pending operation."""
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import Appointment
from conftest import book, proposal, turn


@pytest.mark.parametrize("pending", ["create", "reschedule", "cancel"])
@pytest.mark.parametrize("confirmation,target", [
    ("confirm booking", "create"),
    ("confirm reschedule", "reschedule"),
    ("confirm cancellation", "cancel"),
])
def test_named_confirmation_matches_pending_operation(client, pending, confirmation, target):
    original = None
    if pending == "create":
        c = proposal(client)
    else:
        c = book(client)
        original = c["appointment"]
        c = turn(client, c, "reschedule it to Friday at 4 PM" if pending == "reschedule" else "cancel my confirmed appointment")
    assert c["proposed_action"] == pending
    c = turn(client, c, confirmation)

    if pending == target:
        assert c["last_decision"]["matched_rule"] == "commit.confirmed"
        assert c["last_committed_action"] == pending
        assert c["appointment"]["status"] == ("cancelled" if pending == "cancel" else "confirmed")
        if pending == "reschedule":
            assert c["appointment"]["starts_at"] == "2026-10-30T16:00:00+05:00"
    else:
        assert c["last_decision"]["matched_rule"] == "confirmation.target_mismatch"
        assert c["proposed_action"] is None
        c = turn(client, c, "yes")
        assert c["last_decision"]["matched_rule"] == "confirmation.no_proposal"
        if original:
            assert client.get(f"/api/appointments/{original['reference']}").json() == original
        else:
            assert c["appointment"] is None

    with Session(client.app.state.database.engine) as db:
        assert db.scalar(select(func.count()).select_from(Appointment)) == (1 if original or pending == target else 0)
