"""WebSocket tests for /ws/calls using TestClient and FakeSTT / FakeTTS."""

from __future__ import annotations

import json
from datetime import date, time
from typing import Any

import pytest
from starlette.testclient import TestClient
from voice_agent.brain import responses
from voice_agent.stt.fake_stt import FakeSTT
from voice_agent.tts.fake_tts import FakeTTS

from app.config import settings
from app.main import create_app


class FakeTestClock:
    """Deterministic clock set to Tuesday 2026-10-27."""

    def today(self) -> date:
        return date(2026, 10, 27)

    def now_time(self) -> time:
        return time(10, 0)


class FakeTestGateway:
    """Deterministic in-memory gateway for WebSocket tests."""

    def __init__(self) -> None:
        self.bookings: list[dict[str, Any]] = []

    def free_slots(self, day: date) -> list[Any]:
        from voice_agent.ports import SlotInfo

        return [
            SlotInfo(day, time(9, 0), time(9, 30)),
            SlotInfo(day, time(10, 0), time(10, 30)),
            SlotInfo(day, time(11, 0), time(11, 30)),
        ]

    def book(self, patient_name: str, patient_phone: str, service: str, slot: Any) -> str | None:
        booking_id = f"book-{len(self.bookings) + 1}"
        self.bookings.append(
            {
                "id": booking_id,
                "patient_name": patient_name,
                "patient_phone": patient_phone,
                "service": service,
                "slot": slot,
            }
        )
        return booking_id

    def cancel(self, booking_id: str) -> bool:
        return True

    def reschedule(self, booking_id: str, new_slot: Any) -> str | None:
        return booking_id

    def find_upcoming_by_phone(self, phone: str) -> list[tuple[str, Any]]:
        return []


@pytest.fixture
def ws_client() -> TestClient:
    """Configure TestClient with FakeSTT, FakeTTS, FakeClock, and FakeGateway."""
    app = create_app()
    app.state.stt = FakeSTT()
    app.state.tts = FakeTTS(fixed_bytes=b"FAKE_AUDIO_SAMPLE")
    app.state.clock = FakeTestClock()
    app.state.gateway = FakeTestGateway()
    app.state.active_calls = 0
    return TestClient(app)


def test_ws_greeting_turn_0(ws_client: TestClient) -> None:
    """On connection, server immediately sends greeting turn 0 with audio."""
    with ws_client.websocket_connect("/ws/calls") as ws:
        greeting_raw = ws.receive_text()
        data = json.loads(greeting_raw)

        assert data["type"] == "turn"
        assert data["turn"] == 0
        assert data["reply_text"] == responses.GREETING
        assert data["state"] == "START"
        assert data["end_call"] is False
        assert data["audio"] is not None
        assert "tts_ms" in data["timings"]


def test_ws_full_booking_by_text(ws_client: TestClient) -> None:
    """Full booking dialog completed entirely via JSON user_text frames."""
    with ws_client.websocket_connect("/ws/calls") as ws:
        # Turn 0 greeting
        t0 = json.loads(ws.receive_text())
        assert t0["turn"] == 0

        # Turn 1: Service
        ws.send_text(json.dumps({"type": "user_text", "text": "I want a cleaning"}))
        t1 = json.loads(ws.receive_text())
        assert t1["turn"] == 1
        assert t1["reply_text"] == responses.ASK_DATE

        # Turn 2: Date
        ws.send_text(json.dumps({"type": "user_text", "text": "tomorrow"}))
        t2 = json.loads(ws.receive_text())
        assert t2["turn"] == 2
        assert t2["reply_text"] == responses.ASK_TIME

        # Turn 3: Time
        ws.send_text(json.dumps({"type": "user_text", "text": "10 am"}))
        t3 = json.loads(ws.receive_text())
        assert t3["turn"] == 3
        assert t3["reply_text"] == responses.ASK_NAME

        # Turn 4: Name
        ws.send_text(json.dumps({"type": "user_text", "text": "Sara Khan"}))
        t4 = json.loads(ws.receive_text())
        assert t4["turn"] == 4
        assert t4["reply_text"] == responses.ASK_PHONE

        # Turn 5: Phone
        ws.send_text(json.dumps({"type": "user_text", "text": "03001234567"}))
        t5 = json.loads(ws.receive_text())
        assert t5["turn"] == 5
        assert "0 3 0 0 1 2 3 4 5 6 7" in t5["reply_text"]

        # Turn 6: Confirm Phone
        ws.send_text(json.dumps({"type": "user_text", "text": "yes"}))
        t6 = json.loads(ws.receive_text())
        assert t6["turn"] == 6
        assert "Sara Khan" in t6["reply_text"]

        # Turn 7: Confirm Booking
        ws.send_text(json.dumps({"type": "user_text", "text": "yes"}))
        t7 = json.loads(ws.receive_text())
        assert t7["turn"] == 7
        assert "confirmed" in t7["reply_text"]

        # Call ended frame
        end_frame = json.loads(ws.receive_text())
        assert end_frame["type"] == "call_ended"
        assert end_frame["reason"] == "completed"


def test_ws_audio_turn_via_fake_stt(ws_client: TestClient) -> None:
    """Binary audio frame decoded by FakeSTT and processed by dialog pipeline."""
    with ws_client.websocket_connect("/ws/calls") as ws:
        # Turn 0
        json.loads(ws.receive_text())

        # Send audio turn (FakeSTT decodes UTF-8 bytes)
        ws.send_bytes(b"cancel my appointment")
        res = json.loads(ws.receive_text())

        assert res["turn"] == 1
        assert res["user_text"] == "cancel my appointment"
        assert res["reply_text"] == responses.CANCEL_ASK_PHONE


def test_ws_bad_json(ws_client: TestClient) -> None:
    """Malformed JSON returns error frame without disconnecting the caller."""
    with ws_client.websocket_connect("/ws/calls") as ws:
        # Turn 0
        json.loads(ws.receive_text())

        # Send invalid JSON
        ws.send_text("this is not json")
        err = json.loads(ws.receive_text())

        assert err["type"] == "error"
        assert err["error"] == "bad_json"

        # Subsequent message still works
        ws.send_text(json.dumps({"type": "user_text", "text": "book checkup"}))
        reply = json.loads(ws.receive_text())
        assert reply["turn"] == 1
        assert reply["reply_text"] == responses.ASK_DATE


def test_ws_oversize_audio(ws_client: TestClient) -> None:
    """Binary frame exceeding max_audio_bytes returns oversize_audio error."""
    with ws_client.websocket_connect("/ws/calls") as ws:
        # Turn 0
        json.loads(ws.receive_text())

        # Audio exceeds 1 MB limit
        oversized = b"0" * (settings.max_audio_bytes + 1024)
        ws.send_bytes(oversized)
        err = json.loads(ws.receive_text())

        assert err["type"] == "error"
        assert err["error"] == "oversize_audio"


def test_ws_end_message(ws_client: TestClient) -> None:
    """Client sending {"type": "end"} terminates the call cleanly."""
    with ws_client.websocket_connect("/ws/calls") as ws:
        # Turn 0
        json.loads(ws.receive_text())

        ws.send_text(json.dumps({"type": "end"}))
        ended = json.loads(ws.receive_text())

        assert ended["type"] == "call_ended"
        assert ended["reason"] == "user_hangup"


def test_ws_busy_rejection(ws_client: TestClient) -> None:
    """When active calls reach MAX_CONCURRENT_CALLS, connection receives busy error."""
    ws_client.app.state.active_calls = settings.max_concurrent_calls

    with ws_client.websocket_connect("/ws/calls") as ws:
        err = json.loads(ws.receive_text())
        assert err["type"] == "error"
        assert err["error"] == "busy"
