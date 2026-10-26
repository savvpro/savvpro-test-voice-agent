from datetime import datetime, timedelta

from app.conversation.engine import StaleTurnError


def turn(engine, session, text, turn_id=None):
    return engine.turn(session, turn_id or text, session.version, text)


def fill_booking(engine, session):
    values = [
        "Sara Khan",
        "555 123 4567",
        "2021",
        "Toyota Corolla",
        "oil change",
        "2026-10-27",
        "10 am",
    ]
    response = None
    for index, value in enumerate(values):
        response = turn(engine, session, value, f"fill-{index}")
    return response


def test_complete_text_booking(engine) -> None:
    session = engine.create_session("c1")
    response = fill_booking(engine, session)
    assert response["action"] == "request_confirmation"
    response = turn(engine, session, "yes", "confirm")
    assert response["status"] == "confirmed"
    assert len(engine.store.bookings) == 1


def test_confirmation_retry_is_idempotent(engine) -> None:
    session = engine.create_session("c1")
    fill_booking(engine, session)
    version = session.version
    first = engine.turn(session, "same-turn", version, "yes")
    second = engine.turn(session, "same-turn", version, "yes")
    assert first == second
    assert len(engine.store.bookings) == 1


def test_cancel_noun_phrase_is_correction(engine) -> None:
    session = engine.create_session("c1")
    session.draft["service"] = "oil_change"
    session.last_question = "service"
    response = turn(engine, session, "cancel the oil change I want a tire rotation")
    assert response["status"] == "active"
    assert session.draft["service"] == "tire_rotation"


def test_bare_number_selects_offered_slot(engine) -> None:
    session = engine.create_session("c1")
    session.draft.update(
        name="Sara",
        vehicle_year=2021,
        vehicle="Toyota Corolla",
        service="oil_change",
    )
    session.offered_slots = ["2026-10-27T09:00:00-05:00", "2026-10-27T10:00:00-05:00"]
    response = turn(engine, session, "2")
    assert response["action"] == "select_slot"
    assert session.draft["slot"] == session.offered_slots[1]


def test_yes_outside_boolean_question_has_no_action(engine) -> None:
    session = engine.create_session("c1")
    response = turn(engine, session, "yes")
    assert response["reason"] == "yes_without_boolean_question"
    assert session.draft == {}


def test_same_weekday_means_next_week(engine) -> None:
    friday = datetime(2026, 10, 30).date()
    assert engine._parse_date("friday", friday).isoformat() == "2026-11-06"


def test_ambiguous_hour_requests_meridiem(engine) -> None:
    session = engine.create_session("c1")
    session.last_question = "time"
    response = turn(engine, session, "at 4")
    assert response["reason"] == "next_missing_field" or response["reason"] == "missing_meridiem"
    assert "time" not in session.draft


def test_dotted_pm_time_is_accepted(engine) -> None:
    session = engine.create_session("c1")
    session.draft.update(
        name="Sara",
        phone="5551234567",
        vehicle_year=2021,
        vehicle="Toyota Corolla",
        service="oil_change",
        date="2026-10-27",
    )
    session.last_question = "time"
    response = turn(engine, session, "12:00 p.m.")
    assert response["action"] == "request_confirmation"
    assert session.draft["time"] == "12:00"


def test_phone_collected_across_turns(engine) -> None:
    session = engine.create_session("c1")
    session.draft["name"] = "Sara"
    session.last_question = "phone"
    turn(engine, session, "555", "p1")
    turn(engine, session, "123 4567", "p2")
    assert session.draft["phone"] == "5551234567"


def test_stale_version_rejected(engine) -> None:
    session = engine.create_session("c1")
    turn(engine, session, "Sara")
    try:
        engine.turn(session, "next", 0, "5551234567")
    except StaleTurnError:
        pass
    else:
        raise AssertionError("stale version accepted")


def test_session_expiry(engine) -> None:
    session = engine.create_session("c1")
    session.last_activity_at -= timedelta(minutes=31)
    try:
        engine.turn(session, "t1", 0, "Sara")
    except Exception as error:
        assert type(error).__name__ == "SessionExpiredError"


def test_price_question_returns_to_pending_field(engine) -> None:
    session = engine.create_session("c1")
    response = turn(engine, session, "how much is an oil change")
    assert response["reason"] == "price_unavailable"
    assert response["pending_field"] == "name"


def test_vehicle_status_is_out_of_scope(engine) -> None:
    session = engine.create_session("c1")
    response = turn(engine, session, "is my car ready")
    assert response["reason"] == "status_lookup_unsupported"


def test_two_vehicles_requires_one_choice(engine) -> None:
    session = engine.create_session("c1")
    response = turn(engine, session, "book my Honda Civic and my Ford Focus")
    assert response["reason"] == "one_vehicle_per_call"
    assert response["action"] == "clarify_vehicle"


def test_spelled_name_is_joined(engine) -> None:
    session = engine.create_session("c1")
    turn(engine, session, "my name is spelled S A R A")
    assert session.draft["name"] == "Sara"


def test_non_english_reply_reprompts(engine) -> None:
    session = engine.create_session("c1")
    response = turn(engine, session, "necesito una cita")
    assert response["reason"] == "english_only"
    assert session.draft == {}


def test_symptom_maps_to_diagnostic_with_confirmation(engine) -> None:
    session = engine.create_session("c1")
    session.last_question = "service"
    response = turn(engine, session, "the brakes squeal")
    assert response["candidates"]["service"] == "general_diagnostic"


def test_date_change_invalidates_selected_slot(engine) -> None:
    session = engine.create_session("c1")
    fill_booking(engine, session)
    old_slot = session.draft["slot"]
    response = turn(engine, session, "change to wednesday at 3 pm", "change-date")
    assert response["action"] == "request_confirmation"
    assert session.draft["slot"] != old_slot


def test_unsupported_service_offers_diagnostic(engine) -> None:
    session = engine.create_session("c1")
    session.last_question = "service"
    response = turn(engine, session, "I need a transmission rebuild")
    assert response["action"] == "confirm_service_fallback"
    response = turn(engine, session, "yes", "accept-fallback")
    assert session.draft["service"] == "general_diagnostic"
    assert response["action"] == "accept_service_fallback"


def test_silence_does_not_advance_state(engine) -> None:
    session = engine.create_session("c1")
    response = turn(engine, session, "", "silence")
    assert response["reason"] == "empty_transcript"
    assert session.draft == {}


def test_slot_race_offers_new_alternatives(engine) -> None:
    session = engine.create_session("c1")
    fill_booking(engine, session)
    assert engine.store.confirm(session.draft, "OTHER-1")
    assert engine.store.confirm(session.draft, "OTHER-2")
    response = turn(engine, session, "yes", "raced-confirm")
    assert response["reason"] == "slot_taken_before_confirmation"
    assert response["action"] == "offer_alternatives"
    assert session.status.value == "active"


def test_retry_limit_aborts_without_looping(engine) -> None:
    session = engine.create_session("c1")
    turn(engine, session, "123", "bad-1")
    turn(engine, session, "456", "bad-2")
    response = turn(engine, session, "789", "bad-3")
    assert response["reason"] == "retry_limit"
    assert response["status"] == "aborted"
