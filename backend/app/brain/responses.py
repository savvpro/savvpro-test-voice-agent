"""Response templates for the voice assistant.

Each function returns a natural-language response string.
All responses are deterministic — no LLM, no randomness.
"""

from datetime import datetime

# ---------------------------------------------------------------------------
# Date / time formatting helpers
# ---------------------------------------------------------------------------

_ORDINAL_SUFFIXES = {1: "st", 2: "nd", 3: "rd", 21: "st", 22: "nd", 23: "rd", 31: "st"}


def _ordinal(n: int) -> str:
    return f"{n}{_ORDINAL_SUFFIXES.get(n, 'th')}"


def format_date(iso_date: str) -> str:
    """Format an ISO date as a friendly string, e.g. 'Friday, January 5th'."""
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    day_name = dt.strftime("%A")
    month_name = dt.strftime("%B")
    return f"{day_name}, {month_name} {_ordinal(dt.day)}"


def format_time(hhmm: str) -> str:
    """Format a 24-h time string as '7:30 PM'."""
    dt = datetime.strptime(hhmm, "%H:%M")
    formatted = dt.strftime("%I:%M %p").lstrip("0")
    return formatted


# ---------------------------------------------------------------------------
# Greeting & welcome
# ---------------------------------------------------------------------------

def greeting() -> str:
    return (
        "Welcome to The Golden Fork! I'd be happy to help you make a "
        "reservation. What date would you like to book?"
    )


# ---------------------------------------------------------------------------
# Asking for information
# ---------------------------------------------------------------------------

def ask_date() -> str:
    return "What date would you like to reserve?"


def ask_date_after_info(info_summary: str) -> str:
    return f"Got it — {info_summary}. Now, what date would you like to reserve?"


def ask_time() -> str:
    return "What time would you prefer?"


def ask_time_after_date(date_str: str) -> str:
    return f"Great, {format_date(date_str)}! What time would you prefer?"


def ask_party_size() -> str:
    return "How many guests will be dining?"


def ask_party_size_after_time(time_str: str) -> str:
    return f"Perfect, {format_time(time_str)}. How many guests will be dining?"


# ---------------------------------------------------------------------------
# Confirmation
# ---------------------------------------------------------------------------

def ask_confirmation() -> str:
    return (
        "Please confirm your reservation by saying 'yes' or 'book it', "
        "or tell me what you'd like to change."
    )


def confirm_details(date: str, time: str, party_size: int) -> str:
    guest_word = "guest" if party_size == 1 else "guests"
    return (
        f"Let me confirm your reservation:\n\n"
        f"📅 Date: {format_date(date)}\n"
        f"🕐 Time: {format_time(time)}\n"
        f"👥 Guests: {party_size} {guest_word}\n\n"
        f"Shall I go ahead and book this?"
    )


def booking_confirmed(date: str, time: str, party_size: int) -> str:
    guest_word = "guest" if party_size == 1 else "guests"
    return (
        f"Your reservation has been confirmed! 🎉\n\n"
        f"📅 {format_date(date)}\n"
        f"🕐 {format_time(time)}\n"
        f"👥 {party_size} {guest_word}\n\n"
        f"We look forward to seeing you at The Golden Fork!"
    )


# ---------------------------------------------------------------------------
# Corrections & changes
# ---------------------------------------------------------------------------

def ask_what_to_change() -> str:
    return (
        "No problem! What would you like to change? "
        "You can say things like 'change the date', 'change the time', "
        "or 'change the number of guests'."
    )


def date_updated(new_date: str) -> str:
    return f"Date updated to {format_date(new_date)}."


def time_updated(new_time: str) -> str:
    return f"Time updated to {format_time(new_time)}."


def party_size_updated(new_size: int) -> str:
    guest_word = "guest" if new_size == 1 else "guests"
    return f"Updated to {new_size} {guest_word}."


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

def invalid_date() -> str:
    return (
        "That isn't a valid calendar date. Could you provide a valid date, "
        "such as 'February 28' or '2026-11-15'?"
    )


def invalid_time() -> str:
    return (
        "That isn't a valid time. Please provide a valid time, "
        "such as '7 PM' or '19:30'."
    )


def ambiguous_time() -> str:
    return "I heard more than one time. Please choose one time for your reservation."


def invalid_date_past() -> str:
    return (
        "That date is in the past. Could you please choose a future date?"
    )


def invalid_date_too_far() -> str:
    return (
        "We accept reservations up to 90 days in advance. "
        "Could you pick a closer date?"
    )


def invalid_time_outside_hours() -> str:
    return (
        "Our restaurant is open from 11:00 AM to 10:00 PM, "
        "with last seating at 9:30 PM. "
        "Could you choose a time within those hours?"
    )


def invalid_party_size_zero() -> str:
    return "The number of guests must be at least 1. How many will be dining?"


def invalid_party_size_too_large(maximum: int) -> str:
    return (
        f"We can accommodate up to {maximum} guests per reservation. "
        f"For larger parties, please call us directly. "
        f"How many guests will be dining?"
    )


def could_not_understand_date() -> str:
    return (
        "I didn't quite catch the date. Could you say it again? "
        "For example, 'tomorrow', 'next Friday', or 'January 15th'."
    )


def could_not_understand_time() -> str:
    return (
        "I didn't catch the time. Could you say it again? "
        "For example, '7 PM', '7:30 PM', or 'noon'."
    )


def could_not_understand_party_size() -> str:
    return (
        "I didn't catch the number of guests. Could you say it again? "
        "For example, '4 people', 'for 2', or 'just me'."
    )


def could_not_understand() -> str:
    return (
        "I'm sorry, I didn't understand that. "
        "I'm here to help you make a restaurant reservation. "
        "Could you tell me the date, time, or number of guests?"
    )


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------

def help_message() -> str:
    return (
        "I can help you reserve a table at The Golden Fork! "
        "Just tell me:\n\n"
        "• The date you'd like to visit (e.g. 'tomorrow', 'next Friday')\n"
        "• The time (e.g. '7 PM', '19:00')\n"
        "• How many guests (e.g. '4 people', 'for 2')\n\n"
        "You can also say 'change the date', 'change the time', "
        "'start over', or 'cancel' at any point."
    )


def cancelled() -> str:
    return (
        "Your reservation has been cancelled. "
        "If you'd like to start a new reservation, just say 'start over'."
    )


def already_completed() -> str:
    return (
        "Your reservation is already confirmed! "
        "Changes to a completed reservation aren't supported in this conversation. "
        "Please contact the restaurant to change it, "
        "or say 'start over' to begin a new reservation."
    )


def slot_unavailable() -> str:
    return (
        "I'm sorry, no suitable table is available for that time. "
        "What other time would you prefer? You can also change the date or cancel."
    )


def details_expired() -> str:
    return (
        "Those reservation details can no longer be booked. "
        "Please choose a valid date within the next 90 days."
    )


def restarted() -> str:
    return (
        "No problem, let's start fresh! "
        "What date would you like to reserve?"
    )
