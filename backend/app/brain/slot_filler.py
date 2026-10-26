"""Slot filler — stateless helper that extracts all slots from a turn.

All state lives in the :class:`SlotMap` stored in the session.
This module never reads the system clock.
"""

from __future__ import annotations

from datetime import datetime

from app.brain.date_parser import parse_date_and_period
from app.brain.extractor import extract_phone_last4, extract_tracking_ids
from app.brain.normalizer import NormalizeResult
from app.models.session import SlotMap


def fill_from_turn(
    slot_map: SlotMap,
    norm: NormalizeResult,
    clock: datetime,
    state: str,
) -> dict[str, object]:
    """Extract all available slots from a single turn.

    Modifies *slot_map* in place and returns a dict of slot names → values
    that were extracted in this turn (for the ``DecisionTrace``).

    Args:
        slot_map: The mutable slot map from the session.
        norm: The ``NormalizeResult`` from the normalizer.
        clock: Injected datetime — never reads system clock.
        state: The current dialogue state name (e.g. ``"COLLECT_TRACKING_ID"``).

    Returns:
        A dict of ``{slot_name: extracted_value}`` for tracing.
    """
    extracted: dict[str, object] = {}

    # ── Tracking ID ───────────────────────────────────────────────────
    if state in (
        "COLLECT_TRACKING_ID",
        "CONFIRM_TRACKING_ID",
        "GREETING",
    ):
        ids = extract_tracking_ids(norm.digit_text)
        if len(ids) == 1:
            slot_map.tracking_id = ids[0]
            slot_map.ambiguous_ids = []
            extracted["tracking_id"] = ids[0]
        elif len(ids) >= 2:
            slot_map.ambiguous_ids = ids
            # Do NOT fill tracking_id — state machine asks caller to choose.
            extracted["ambiguous_ids"] = ids

    # ── Phone last 4 ─────────────────────────────────────────────────
    if state == "VERIFY_PHONE":
        # The tracking ID was provided on an earlier turn. Excluding its digits
        # here would reject a valid phone number such as 1234 whenever it also
        # appears inside that ID. Any ID present in this turn is filtered by
        # the extractor's tracking-ID span check.
        last4 = extract_phone_last4(norm.digit_text)
        if last4:
            slot_map.phone_last4 = last4
            extracted["phone_last4"] = last4

    # ── Date and period ───────────────────────────────────────────────
    if state in ("COLLECT_DATE", "COLLECT_PERIOD", "CONFIRM_SLOT"):
        result = parse_date_and_period(norm.digit_text, clock)

        if result.date is not None:
            if result.reason is None:
                slot_map.intended_date = result.date
                extracted["intended_date"] = result.date.isoformat()
            else:
                extracted["date_rejection"] = result.reason
                extracted["rejected_date"] = result.date.isoformat()

        if result.period is not None:
            if result.reason is None:
                slot_map.intended_period = result.period
                extracted["intended_period"] = result.period
            elif result.reason == "cutoff":
                extracted["period_cutoff"] = result.period

    return extracted


def missing_required_slots(slot_map: SlotMap, state: str) -> list[str]:
    """Return a list of slot names still needed for the current state.

    Args:
        slot_map: The session's slot map.
        state: The current dialogue state name.

    Returns:
        A list of missing slot name strings.
    """
    missing: list[str] = []

    if state == "COLLECT_TRACKING_ID" and not slot_map.tracking_id:
        missing.append("tracking_id")
    elif state == "VERIFY_PHONE" and not slot_map.phone_last4:
        missing.append("phone_last4")
    elif state == "COLLECT_DATE" and not slot_map.intended_date:
        missing.append("intended_date")
    elif state == "COLLECT_PERIOD" and not slot_map.intended_period:
        missing.append("intended_period")
    elif state == "COLLECT_PICKUP_POINT" and not slot_map.pickup_point_id:
        missing.append("pickup_point_id")

    return missing


def reset_date_slots(slot_map: SlotMap) -> None:
    """Clear date-related slots for a fresh date collection.

    Per PLAN §5: resetting ``intended_date`` also resets ``intended_period``
    and ``confirmed_slot_id``.
    """
    slot_map.intended_date = None
    slot_map.intended_period = None
    slot_map.confirmed_slot_id = None


def reset_action_slots(slot_map: SlotMap) -> None:
    """Clear all action-related slots for a return to CHOOSE_ACTION.

    Per PLAN §5: resetting ``action_intent`` also resets all date, period,
    slot, and pickup slots.
    """
    slot_map.action_intent = None
    slot_map.intended_date = None
    slot_map.intended_period = None
    slot_map.confirmed_slot_id = None
    slot_map.pickup_point_id = None
    slot_map.cancel_confirmed = False
