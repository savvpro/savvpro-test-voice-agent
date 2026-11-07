"""Canonical repository of all reply texts used by the brain.

Per AGENTS.md Rule 4:
All reply text lives in ai-tool/src/voice_agent/brain/responses.py.
No reply text elsewhere.
"""

from __future__ import annotations

from collections.abc import Sequence

# ── Greetings and Closings ───────────────────────────────────────────────────

GREETING = "Hello, thank you for calling BrightSmile Dental Clinic. How can I help you today?"
GOODBYE = "Thank you for calling BrightSmile Dental Clinic. Have a wonderful day! Goodbye."
MAX_TURNS_END = (
    "Thank you for calling BrightSmile Dental Clinic. For further assistance, "
    "please visit our clinic or call our front desk directly. Goodbye!"
)
HANDOFF = (
    "I'm having a little trouble understanding. Let me connect you with our front desk "
    "staff who can assist you further. Please hold."
)

# ── General Fallbacks & Off-Topic ────────────────────────────────────────────

FALLBACK = "I'm sorry, I didn't quite catch that. Could you please repeat that?"
OFF_TOPIC = (
    "I can only help with booking, rescheduling, or cancelling dental appointments at "
    "BrightSmile Dental Clinic. Would you like to book, reschedule, or cancel?"
)

# ── Booking Flow ─────────────────────────────────────────────────────────────

ASK_SERVICE = (
    "What service do you need? We offer cleaning, checkup, filling, whitening, "
    "root canal, and braces consultation."
)
ASK_DATE = "What day would you like to come in?"
ASK_TIME = "What time works best for you? We are open Monday to Saturday from 9 AM to 5 PM."
CLARIFY_TIME_MORNING_EVENING = "Did you mean morning or evening?"
CLARIFY_TIME_OFF_HOURS = (
    "Our clinic hours are Monday through Saturday, 9 AM to 5 PM, and we are closed on Sundays. "
    "Could you choose a time during our working hours?"
)
CLARIFY_CLOSED_SUNDAY = (
    "We are closed on Sundays. Would you like to choose a Monday through Saturday instead?"
)


def format_offer_alternatives(slot1: str, slot2: str) -> str:
    """Format prompt offering two nearest available alternatives."""
    return f"That slot is not available. Would {slot1} or {slot2} work for you?"


def format_offer_no_slots(date_str: str) -> str:
    """Format reply when an entire day has no free slots."""
    return f"I'm sorry, we have no available appointments on {date_str}. Would you like to check another day?"


ASK_NAME = "May I please have your full name?"
ASK_PHONE = "Could you please provide your phone number?"
INVALID_PHONE = "Please provide a valid phone number with 7 to 15 digits."


def format_confirm_phone(phone_digits: str) -> str:
    """Read back phone digit by digit for confirmation."""
    return f"I have your phone number as {' '.join(phone_digits)}. Is that correct?"


def format_confirm_booking(name: str, service: str, date_str: str, time_str: str) -> str:
    """Format booking summary for confirmation."""
    return f"I have a {service} for {name} on {date_str} at {time_str}. May I confirm this booking?"


def format_booking_success(date_str: str, time_str: str) -> str:
    """Format successful booking response."""
    return f"Your appointment is confirmed for {date_str} at {time_str}. We look forward to seeing you!"


def format_booking_race_lost(slot1: str, slot2: str) -> str:
    """Format message when another caller books the slot right before confirmation."""
    return (
        f"I apologize, that slot was just taken by another caller. "
        f"Would {slot1} or {slot2} work for you instead?"
    )


def format_duplicate_booking(date_str: str, time_str: str) -> str:
    """Format message when caller already has a booking at the requested time."""
    return (
        f"You already have a confirmed appointment on {date_str} at {time_str}. "
        "Would you like to reschedule or cancel it instead?"
    )


# ── Cancel Flow ──────────────────────────────────────────────────────────────

CANCEL_ASK_PHONE = "Could you please provide your phone number so I can look up your appointment?"
CANCEL_NO_APPOINTMENTS = (
    "I couldn't find any upcoming appointments for that phone number. "
    "Would you like to book a new appointment?"
)


def format_cancel_choose_which(options: Sequence[str]) -> str:
    """Prompt caller to choose which appointment to cancel."""
    opts_str = " or ".join(options)
    return f"You have upcoming appointments on {opts_str}. Which one would you like to cancel?"


def format_cancel_confirm(date_str: str, time_str: str) -> str:
    """Ask caller to confirm cancellation."""
    return f"Are you sure you want to cancel your appointment on {date_str} at {time_str}?"


def format_cancel_success(date_str: str, time_str: str) -> str:
    """Confirm cancellation."""
    return f"Your appointment on {date_str} at {time_str} has been cancelled."


# ── Reschedule Flow ──────────────────────────────────────────────────────────

RESCHEDULE_ASK_NEW_TIME = "What new date and time would you prefer?"


def format_reschedule_confirm(old_date: str, old_time: str, new_date: str, new_time: str) -> str:
    """Ask caller to confirm rescheduling."""
    return (
        f"Are you sure you want to move your appointment from {old_date} at {old_time} "
        f"to {new_date} at {new_time}?"
    )


def format_reschedule_success(new_date: str, new_time: str) -> str:
    """Confirm successful rescheduling."""
    return f"Your appointment has been successfully rescheduled to {new_date} at {new_time}."


def format_reschedule_unavailable(slot1: str, slot2: str) -> str:
    """Format message when new reschedule slot is unavailable."""
    return f"That slot is not available. Would {slot1} or {slot2} work instead?"
