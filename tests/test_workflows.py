from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import store
from backend.database import Allocation, Appointment, Bay, CallerSession
from backend.domain import local_slot
from tests.conftest import NOW, start, turn


def test_seed_and_initialization_idempotent(client: TestClient) -> None:
    initial = start(client)
    assert len(initial["appointments"]) == 1
    assert initial["appointments"][0]["time"] == "11:00"
    assert initial["appointments"][0]["service"] == "tyre_rotation"
    assert start(client) == initial


def test_book_and_two_segment_allocation(client: TestClient) -> None:
    start(client)
    result = turn(client, "Book a brake inspection for my SUV tomorrow at 3 PM")
    assert result["state"]["phase"] == "CONFIRMING"
    assert len(result["appointments"]) == 1
    booked = turn(client, "yes")
    assert booked["trace"]["action"] == "booked"
    assert len(booked["appointments"]) == 2
    with Session(client.app.state.engine) as db:
        allocations = list(
            db.scalars(
                select(Allocation).where(
                    Allocation.appointment_id == booked["state"]["appointment"]["id"]
                )
            )
        )
        assert len(allocations) == 2
        assert allocations[0].bay_id == allocations[1].bay_id


def test_conflict_and_alternative_selection(client: TestClient) -> None:
    start(client)
    result = turn(client, "Book a brake inspection for my SUV tomorrow at 2 PM")
    assert "both_bays_occupied" in result["trace"]["validation"]
    assert len(result["state"]["alternatives"]) == 3
    choice = result["state"]["alternatives"][0]
    result = turn(client, "first one")
    assert result["state"]["phase"] == "CONFIRMING"
    assert result["state"]["slots"]["time"] == choice["time"]


def test_overrun_rejected(client: TestClient) -> None:
    start(client)
    result = turn(client, "Book a brake inspection for my SUV tomorrow at 5:30 PM")
    assert "must finish by 6 PM" in result["reply"]
    assert result["state"]["phase"] == "COLLECTING"
    assert "time" not in result["state"]["slots"]


def test_spoken_number_selects_alternative_not_clock_time(client: TestClient) -> None:
    start(client)
    proposed = turn(client, "Book a brake inspection for my SUV tomorrow at 2 PM")
    alternative = proposed["state"]["alternatives"][1]
    result = turn(client, "option two.")
    assert result["state"]["slots"]["time"] == alternative["time"]
    assert result["state"]["slots"]["date"] == alternative["date"]


def test_correction_invalidates_confirmation(client: TestClient) -> None:
    start(client)
    turn(client, "Book an oil change for my car tomorrow at 10 AM")
    result = turn(client, "yes, actually make that Thursday at 11 AM")
    assert result["state"]["phase"] == "CONFIRMING"
    assert len(result["appointments"]) == 1
    assert result["state"]["slots"]["date"] == "2026-10-29"
    booked = turn(client, "yes")
    assert booked["state"]["appointment"]["date"] == "2026-10-29"


def test_collect_slots_and_ancillary_question_preserves_draft(client: TestClient) -> None:
    start(client)
    turn(client, "I'd like to book")
    turn(client, "oil change")
    turn(client, "car")
    turn(client, "tomorrow")
    reply = turn(client, "What time do you close?")
    assert "6 PM" in reply["reply"]
    result = turn(client, "ten")
    assert result["state"]["phase"] == "CONFIRMING"
    assert result["state"]["slots"]["service"] == "oil_change"


def test_reschedule_seed_and_cancel(client: TestClient) -> None:
    initial = start(client)
    result = turn(client, "reschedule")
    assert "Tyre Rotation" in result["reply"]
    assert "new date and time" in result["reply"]
    turn(client, "Thursday at 3 PM")
    result = turn(client, "yes")
    assert result["trace"]["action"] == "rescheduled"
    assert result["appointments"][0]["id"] == initial["appointments"][0]["id"]
    assert result["appointments"][0]["date"] == "2026-10-29"
    turn(client, "cancel my appointment")
    result = turn(client, "yes")
    assert result["appointments"] == []
    with Session(client.app.state.engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Allocation)
                .where(Allocation.appointment_id == initial["appointments"][0]["id"])
            )
            == 0
        )


def test_failed_reschedule_preserves_original(client: TestClient) -> None:
    initial = start(client)["appointments"][0]
    reply = turn(client, "Don't cancel it, reschedule it to tomorrow at 2 PM")
    assert "both_bays_occupied" in reply["trace"]["validation"]
    assert reply["appointments"][0] == initial
    turn(client, "no")
    assert start(client)["appointments"][0] == initial


def test_multi_appointment_selection(client: TestClient) -> None:
    start(client)
    turn(client, "Book an oil change for my car Thursday at 10 AM")
    turn(client, "yes")
    result = turn(client, "cancel my appointment")
    assert result["state"]["phase"] == "SELECTING_APPOINTMENT"
    assert "1:" in result["reply"] and "2:" in result["reply"]
    result = turn(client, "second one")
    assert result["state"]["phase"] == "CONFIRMING"
    assert "Oil Change" in result["reply"]
    result = turn(client, "yes")
    assert len(result["appointments"]) == 1
    assert result["appointments"][0]["service"] == "tyre_rotation"


def test_spoken_number_identifies_appointment(client: TestClient) -> None:
    start(client)
    turn(client, "Book an oil change for my car Thursday at 10 AM")
    turn(client, "yes")
    turn(client, "reschedule my appointment")
    selected = turn(client, "number two")
    assert "Oil Change" in selected["reply"]
    assert selected["state"]["needs_new_schedule"] is True


def test_multi_appointment_reschedule_preserves_proposal(client: TestClient) -> None:
    start(client)
    turn(client, "Book an oil change for my car Thursday at 10 AM")
    turn(client, "yes")
    result = turn(client, "move my appointment to Friday at 3 PM")
    assert result["state"]["phase"] == "SELECTING_APPOINTMENT"
    result = turn(client, "oil change")
    assert result["state"]["phase"] == "CONFIRMING"
    assert result["state"]["slots"]["date"] == "2026-10-30"
    assert result["state"]["slots"]["time"] == "15:00"


def test_zero_appointments(client: TestClient) -> None:
    start(client)
    turn(client, "cancel my appointment")
    turn(client, "yes")
    result = turn(client, "reschedule my appointment")
    assert "No active booking" in result["reply"]


def test_declining_and_abandoning_never_mutates(client: TestClient) -> None:
    original = start(client)["appointments"]
    turn(client, "Book an oil change for my car tomorrow at 10 AM")
    turn(client, "cancel that")
    assert start(client)["appointments"] == original
    turn(client, "cancel my appointment")
    turn(client, "no")
    assert start(client)["appointments"] == original


def test_reset_and_stale_turn(client: TestClient) -> None:
    initial = start(client)
    turn(client, "cancel my appointment")
    deleted = turn(client, "yes")
    response = client.post("/api/session/reset", json={"revision": deleted["revision"]})
    assert response.status_code == 200
    assert len(response.json()["appointments"]) == 1
    assert response.json()["history"] == []
    stale = client.post(
        "/api/turn", json={"revision": initial["revision"], "text": "yes", "turn_id": uuid4().hex}
    )
    assert stale.status_code == 409


def test_turn_id_deduplication_and_mismatched_payload(client: TestClient) -> None:
    start(client)
    turn(client, "Book an oil change for my car tomorrow at 10 AM")
    revision = start(client)["revision"]
    key = uuid4().hex
    first = turn(client, "yes", revision, key)
    duplicate = turn(client, "yes", revision, key)
    assert first == duplicate
    assert len(start(client)["appointments"]) == 2
    mismatch = client.post("/api/turn", json={"revision": revision, "text": "no", "turn_id": key})
    assert mismatch.status_code == 409


def test_concurrent_confirmation_exactly_once(client: TestClient) -> None:
    start(client)
    turn(client, "Book a brake inspection for my SUV tomorrow at 3 PM")
    revision = start(client)["revision"]
    payload = {"revision": revision, "text": "yes", "turn_id": uuid4().hex}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post("/api/turn", json=payload), range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    assert len(start(client)["appointments"]) == 2


def test_concurrent_different_turns_reject_stale(client: TestClient) -> None:
    revision = start(client)["revision"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    "/api/turn", json={"revision": revision, "text": "help", "turn_id": uuid4().hex}
                ),
                range(2),
            )
        )
    assert sorted(r.status_code for r in responses) == [200, 409]


def test_database_uniqueness_and_failed_savepoint(client: TestClient) -> None:
    start(client)
    engine = client.app.state.engine
    with Session(engine) as db, db.begin():
        allocation = db.scalar(select(Allocation))
        assert allocation is not None
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                Allocation(
                    bay_id=allocation.bay_id,
                    appointment_id=allocation.appointment_id,
                    segment_start=allocation.segment_start,
                )
            )
            db.flush()
        caller = db.scalar(select(CallerSession))
        assert caller is not None
        original = store.owned(db, caller.id, NOW)[0]
        old_start = original.start
        assert (
            store.reserve(
                db,
                caller.id,
                "brake_inspection",
                "suv",
                local_slot("2026-10-27", "14:00"),
                original,
            )
            is None
        )
        assert original.start == old_start


def test_session_isolation(client: TestClient) -> None:
    start(client)
    original_cookie = client.cookies.get("bayline_session")
    client.cookies.clear()
    second = start(client)
    second_cookie = client.cookies.get("bayline_session")
    assert original_cookie != second_cookie
    turn(client, "cancel my appointment")
    cancelled = turn(client, "yes")
    assert cancelled["appointments"] == []
    client.post("/api/session/reset", json={"revision": cancelled["revision"]})
    client.cookies.set("bayline_session", original_cookie)
    assert len(start(client)["appointments"]) == 1
    with Session(client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Bay)) == 4
    assert len(second["appointments"]) == 1


def test_boundaries_and_capabilities(client: TestClient) -> None:
    assert client.get("/api/appointments").status_code == 401
    assert client.get("/api/health").json()["brain"] == "deterministic-python"
    assert "server_stt" in client.get("/api/capabilities").json()
    assert (
        client.post("/api/session", headers={"Origin": "https://attacker.example"}).status_code
        == 403
    )
    start(client)
    assert (
        client.post(
            "/api/turn", json={"revision": 0, "text": "  ", "turn_id": uuid4().hex}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/turn", json={"revision": 0, "text": "help", "turn_id": "invalid key"}
        ).status_code
        == 422
    )


def test_selection_with_incidental_appointment_word(client: TestClient) -> None:
    start(client)
    turn(client, "Book an oil change for my car Thursday at 10 AM")
    turn(client, "yes")
    turn(client, "move my appointment to Friday at 3 PM")
    result = turn(client, "the oil change appointment")
    assert result["state"]["intent"] == "RESCHEDULE"
    assert result["state"]["slots"]["date"] == "2026-10-30"


def test_confirmation_cannot_transfer_to_a_different_operation(client: TestClient) -> None:
    start(client)
    turn(client, "Book an oil change for my car Thursday at 10 AM")
    result = turn(client, "yes, cancel my appointment")
    assert result["state"]["phase"] == "CONFIRMING"
    assert result["trace"]["action"] == "none"
    assert len(result["appointments"]) == 1
    assert "cancel your" in result["reply"]


def test_cancellation_correction_selects_new_target_and_reconfirms(client: TestClient) -> None:
    start(client)
    turn(client, "Book an oil change for my car Thursday at 10 AM")
    turn(client, "yes")
    turn(client, "cancel my tyre rotation")
    result = turn(client, "actually the oil change instead")
    assert "Oil Change" in result["reply"]
    assert result["trace"]["action"] == "none"
    result = turn(client, "yes")
    assert len(result["appointments"]) == 1
    assert result["appointments"][0]["service"] == "tyre_rotation"


def test_reschedule_partial_insert_rolls_back_original(
    client: TestClient, monkeypatch: Any
) -> None:
    start(client)
    engine = client.app.state.engine
    with Session(engine) as db, db.begin():
        caller = db.scalar(select(CallerSession))
        assert caller is not None
        appointment = store.owned(db, caller.id, NOW)[0]
        old = store.summary(appointment)
        old_allocations = [
            (a.bay_id, a.segment_start)
            for a in db.scalars(
                select(Allocation).where(Allocation.appointment_id == appointment.id)
            )
        ]
        bay = db.scalar(select(Bay).where(Bay.session_id == caller.id, Bay.number == 1))
        assert bay is not None
        # Emulate a bay becoming occupied after the availability read: 13:30 is free, 14:00 is seeded busy.
        monkeypatch.setattr(store, "free_bays", lambda *args: [bay])
        assert (
            store.reserve(
                db,
                caller.id,
                "brake_inspection",
                "car",
                local_slot("2026-10-27", "13:30"),
                appointment,
            )
            is None
        )
        assert store.summary(appointment) == old
        current = [
            (a.bay_id, a.segment_start)
            for a in db.scalars(
                select(Allocation).where(Allocation.appointment_id == appointment.id)
            )
        ]
        assert current == old_allocations


def test_two_transactions_cannot_claim_same_bay_segment(client: TestClient) -> None:
    import threading

    start(client)
    engine = client.app.state.engine
    with Session(engine) as db, db.begin():
        caller = db.scalar(select(CallerSession))
        assert caller is not None
        bay_id = db.scalar(select(Bay.id).where(Bay.session_id == caller.id, Bay.number == 1))
        owners = []
        for _ in range(2):
            appointment = Appointment(
                id=str(uuid4()),
                session_id=caller.id,
                service="oil_change",
                vehicle="car",
                start=store.utc_naive(local_slot("2026-10-27", "10:00")),
                kind="caller",
            )
            db.add(appointment)
            owners.append(appointment.id)
    barrier = threading.Barrier(2)

    def claim(appointment_id: str) -> str:
        try:
            with Session(engine) as db, db.begin():
                barrier.wait(timeout=5)
                db.add(
                    Allocation(
                        bay_id=bay_id,
                        appointment_id=appointment_id,
                        segment_start=store.utc_naive(local_slot("2026-10-27", "10:00")),
                    )
                )
                db.flush()
            return "reserved"
        except IntegrityError:
            return "collision"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, owners))
    assert sorted(outcomes) == ["collision", "reserved"]


def test_future_calendar_seed_on_saturday(tmp_path: Any) -> None:
    from datetime import datetime

    from backend.app import create_app
    from backend.domain import PKT

    app = create_app(
        "sqlite:///" + str(tmp_path / "saturday.db"),
        now=lambda: datetime(2026, 10, 31, 16, tzinfo=PKT),
    )
    with TestClient(app) as browser:
        assert start(browser)["appointments"][0]["date"] == "2026-11-02"
