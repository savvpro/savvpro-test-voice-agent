"""Automated test suite for Tableline backend."""

import pytest
import datetime
from fastapi.testclient import TestClient
from backend.main import app, dialogue_manager, restaurant_service
from backend.models import ConversationState
from backend.parser import DeterministicParser
from backend.dialogue_manager import DialogueManager
from backend.restaurant_service import RestaurantService

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["engine"] == "deterministic"


def test_start_conversation():
    res = client.post("/api/conversation/start")
    assert res.status_code == 200
    data = res.json()
    assert data["conversation_id"].startswith("conv_")
    assert data["state"] == ConversationState.GREETING
    assert "Tableline" in data["assistant_message"]


def test_multi_detail_extraction():
    ref_date = datetime.date(2026, 10, 30)  # A Friday
    parser = DeterministicParser(reference_date=ref_date)
    parsed = parser.parse_utterance("Book a table for 4 people on Friday at 7 PM under John")
    
    assert parsed["guests"] == 4
    assert parsed["time"] == "19:00"
    assert parsed["date"] == "2026-10-30"
    assert parsed["customer_name"] == "John"


def test_party_size_validation():
    ref_date = datetime.date(2026, 10, 30)
    service = RestaurantService()
    dm = DialogueManager(restaurant_service=service, reference_date=ref_date)
    conv_id = "test_party_size"
    
    # Party of 0 / invalid
    res = dm.process_turn(conv_id, "Table for 0 please")
    assert "at least one guest" in res.assistant_message
    
    # Party > 12
    res2 = dm.process_turn(conv_id, "We have 15 people")
    assert "private dining manager" in res2.assistant_message


def test_correction_handling():
    ref_date = datetime.date(2026, 10, 30)  # Friday
    service = RestaurantService()
    dm = DialogueManager(restaurant_service=service, reference_date=ref_date)
    conv_id = "test_correction_session"

    # 1. First statement: 4 people at 7pm on Friday
    t1 = dm.process_turn(conv_id, "Table for 4 this Friday at 7 PM")
    # Friday 7 PM is fully booked in our fictional dataset! Should offer alternatives
    assert t1.state == ConversationState.OFFERING_ALTERNATIVES
    assert len(t1.suggested_alternatives) > 0

    # 2. Correction: "Actually make that 6 people and 8 PM"
    t2 = dm.process_turn(conv_id, "Actually make that 6 people, and 8 PM")
    assert dm.sessions[conv_id].booking_details.guests == 6
    assert dm.sessions[conv_id].booking_details.time == "20:00"
    # Should re-check availability and advance to AWAITING_CONFIRMATION
    assert t2.state == ConversationState.AWAITING_CONFIRMATION
    assert "20:00" in t2.assistant_message
    assert "6 guests" in t2.assistant_message


def test_explicit_confirmation_and_idempotency():
    ref_date = datetime.date(2026, 10, 30)
    service = RestaurantService()
    dm = DialogueManager(restaurant_service=service, reference_date=ref_date)
    conv_id = "test_confirm"

    # Setup ready state
    t1 = dm.process_turn(conv_id, "Book for 2 guests on tomorrow at 6 PM under Alice")
    assert t1.state == ConversationState.AWAITING_CONFIRMATION
    assert not t1.is_confirmed

    # Explicit confirmation
    t2 = dm.process_turn(conv_id, "Yes, confirm it please")
    assert t2.state == ConversationState.CONFIRMED
    assert t2.is_confirmed
    assert t2.reservation_reference is not None
    assert t2.reservation_reference.startswith("TL-")

    ref = t2.reservation_reference

    # Repeated confirmation should be idempotent and not create duplicate
    t3 = dm.process_turn(conv_id, "Yes please confirm")
    assert t3.state == ConversationState.CONFIRMED
    assert t3.reservation_reference == ref

    # Verify stored in service
    stored = service.get_reservation(ref)
    assert stored is not None
    assert stored.guests == 2
    assert stored.customer_name == "Alice"


def test_stale_state_invalidation():
    ref_date = datetime.date(2026, 10, 30)
    service = RestaurantService()
    dm = DialogueManager(restaurant_service=service, reference_date=ref_date)
    conv_id = "test_stale"

    # Get to awaiting confirmation
    dm.process_turn(conv_id, "Table for 2 tomorrow at 6 PM")
    assert dm.sessions[conv_id].state == ConversationState.AWAITING_CONFIRMATION

    # Now caller changes their mind before confirming
    t2 = dm.process_turn(conv_id, "Wait, make it 8 PM instead")
    assert dm.sessions[conv_id].booking_details.time == "20:00"
    assert not dm.sessions[conv_id].is_confirmed


def test_cancellation_and_restart():
    ref_date = datetime.date(2026, 10, 30)
    service = RestaurantService()
    dm = DialogueManager(restaurant_service=service, reference_date=ref_date)
    conv_id = "test_cancel"

    dm.process_turn(conv_id, "Table for 4 tomorrow at 6 PM")
    t_cancel = dm.process_turn(conv_id, "Never mind, cancel it")
    assert t_cancel.state == ConversationState.CANCELLED

    t_restart = dm.process_turn(conv_id, "Let's start over")
    assert t_restart.state == ConversationState.GREETING
    assert dm.sessions[conv_id].booking_details.date is None
