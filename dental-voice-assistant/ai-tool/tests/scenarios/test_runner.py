"""Scenario runner: loads YAML dialog scenarios and validates brain turns."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pytest
import yaml
from fake_services import FakeBookingGateway, FakeClock

from voice_agent.brain.dialog import handle_turn
from voice_agent.brain.state import SessionContext, State
from voice_agent.ports import SlotInfo

SCENARIOS_DIR = Path(__file__).parent
YAML_FILES = sorted(list(SCENARIOS_DIR.glob("case_*.yaml")))


def _parse_time(t_str: str) -> time:
    parts = t_str.split(":")
    return time(int(parts[0]), int(parts[1]))


def _parse_date(d_str: str) -> date:
    return date.fromisoformat(d_str)


@pytest.mark.parametrize("yaml_file", YAML_FILES, ids=lambda p: p.stem)
def test_scenario(yaml_file: Path) -> None:
    data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))

    # 1. Setup clock
    today = _parse_date(data.get("today", "2026-10-27"))
    clock = FakeClock(today)

    # 2. Setup initial slots for gateway
    available_slots: dict[date, list[SlotInfo]] = {}
    for slot_def in data.get("initial_slots", []):
        d = _parse_date(slot_def["date"])
        s = _parse_time(slot_def["start"])
        e = _parse_time(slot_def.get("end", f"{s.hour}:30"))
        available_slots.setdefault(d, []).append(SlotInfo(d, s, e))

    # 3. Setup existing appointments for gateway
    existing_appts: dict[str, list[tuple[str, SlotInfo]]] = {}
    for appt_def in data.get("existing_appointments", []):
        phone = appt_def["phone"]
        aid = appt_def["id"]
        d = _parse_date(appt_def["date"])
        s = _parse_time(appt_def["start"])
        e = _parse_time(appt_def.get("end", f"{s.hour}:30"))
        existing_appts.setdefault(phone, []).append((aid, SlotInfo(d, s, e)))

    # 4. Optional race condition slot simulation
    race_slot = None
    if "race_on_slot" in data:
        r = data["race_on_slot"]
        race_slot = SlotInfo(_parse_date(r["date"]), _parse_time(r["start"]), _parse_time(r["end"]))

    gateway = FakeBookingGateway(
        available_slots=available_slots,
        existing_appointments=existing_appts,
        fail_booking_on_slot=race_slot,
    )

    ctx = SessionContext()
    if "initial_state" in data:
        ctx.state = State(data["initial_state"])
    if "initial_phone" in data:
        ctx.patient_phone = data["initial_phone"]
    if "initial_name" in data:
        ctx.patient_name = data["initial_name"]
    if "initial_turn_count" in data:
        ctx.turn_count = data["initial_turn_count"]

    # 5. Execute turns
    for idx, turn in enumerate(data.get("turns", [])):
        user_input = turn.get("user", "")
        res = handle_turn(user_input, ctx, gateway, clock)

        if "expected_state" in turn:
            assert ctx.state.value == turn["expected_state"], (
                f"Turn {idx + 1} ('{user_input}'): expected state {turn['expected_state']}, got {ctx.state.value}"
            )

        if "expected_reply_contains" in turn:
            expected_substr = turn["expected_reply_contains"].lower()
            assert expected_substr in res.reply_text.lower(), (
                f"Turn {idx + 1} ('{user_input}'): expected reply to contain '{expected_substr}', got '{res.reply_text}'"
            )

        if "expected_end_call" in turn:
            assert res.end_call == turn["expected_end_call"], (
                f"Turn {idx + 1} ('{user_input}'): expected end_call={turn['expected_end_call']}, got {res.end_call}"
            )

        if "expected_action" in turn:
            assert res.action == turn["expected_action"], (
                f"Turn {idx + 1} ('{user_input}'): expected action={turn['expected_action']}, got {res.action}"
            )
