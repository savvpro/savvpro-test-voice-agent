"""
Response templates for the restaurant booking brain.

Keeping them in one place makes the dialogue natural to tweak without
touching the state machine logic. All responses are plain strings so the
frontend TTS can read them directly.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .restaurant import (
    RESTAURANT_NAME, RESTAURANT_PHONE, RESTAURANT_ADDRESS,
    RESTAURANT_CUISINE, STORE,
)


def greet() -> str:
    return (
        f"Thanks for calling {RESTAURANT_NAME}. "
        f"I can help you book a table. What day would you like to come in?"
    )


def ask_date() -> str:
    return "Sure. What day would you like to book?"


def ask_time() -> str:
    return "Great. What time works for you?"


def ask_party_size() -> str:
    return "And how many people will be joining?"


def ask_name() -> str:
    return "Last thing — what name should I put the reservation under?"


def ask_phone() -> str:
    return "And a phone number where we can reach you?"


def confirm(slots: dict) -> str:
    d = _pretty_date(slots.get("date")) if slots.get("date") else "the requested day"
    t = _pretty_time(slots.get("time")) if slots.get("time") else "the requested time"
    party = slots.get("party_size") or "your party"
    name = slots.get("name") or "your name"
    return (
        f"Let me confirm. A table for {party} "
        f"on {d} at {t}, under {name}. "
        f"Should I go ahead and book that?"
    )


def booked(booking_id: str, slots: dict) -> str:
    d = _pretty_date(slots["date"]) if slots.get("date") else "your date"
    t = _pretty_time(slots["time"]) if slots.get("time") else "your time"
    party = slots.get("party_size") or "your party"
    name = slots.get("name") or "your name"
    return (
        f"You're all set. Your reservation is confirmed for {party} "
        f"on {d} at {t}, under {name}. "
        f"Your confirmation number is {booking_id}. "
        f"We'll see you then. Anything else?"
    )


def cancelled() -> str:
    return "No problem, I've cancelled that. Is there anything else I can help with?"


def goodbye() -> str:
    return f"Thank you for calling {RESTAURANT_NAME}. Have a great day. Goodbye."


def not_available(reason: str, alternatives: list[str]) -> str:
    msg = reason
    if alternatives:
        human = ", ".join(_pretty_time(a) for a in alternatives)
        msg += f" The closest available times are {human}. Would any of those work?"
    else:
        msg += " Would you like to try a different day?"
    return msg


def ask_change_what() -> str:
    return "Sure — what would you like to change? The day, the time, or the party size?"


def did_not_understand() -> str:
    return "I'm sorry, I didn't quite catch that. Could you repeat it?"


def hours_info() -> str:
    return (
        f"We're open Tuesday through Friday for lunch from 11:30 to 2 and dinner from 5 to 10, "
        f"Saturday dinner only from 5 to 11, and Sunday from noon to 9. We're closed Mondays. "
        f"What day would you like to book?"
    )


def location_info() -> str:
    return (
        f"We're at {RESTAURANT_ADDRESS}. Our phone number is {RESTAURANT_PHONE}. "
        f"Back to your booking — what day would you like?"
    )


def menu_info() -> str:
    return (
        f"We serve {RESTAURANT_CUISINE}. We're happy to accommodate most dietary needs. "
        f"Back to your booking — what day would you like?"
    )


def parking_info() -> str:
    return (
        "There's a public parking garage one block south, and we offer valet on weekends. "
        "Back to your booking — what day would you like?"
    )


def cannot_help() -> str:
    return (
        "I can only help with booking a table, our hours, location, menu, or parking. "
        "Would you like to book a table?"
    )


def empty_confirm() -> str:
    return "There's nothing to confirm yet. Would you like to book a table?"


def empty_deny() -> str:
    return "I haven't suggested anything yet. Would you like to book a table?"


def repeat_last(prompt: str) -> str:
    return prompt


def silence() -> str:
    return "I didn't hear anything. Are you still there?"


# ---------------------------------------------------------------------------
def _pretty_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
        today = date.today()
        if d == today:
            return "today"
        if d == today + timedelta(days=1):
            return "tomorrow"
        return d.strftime("%A, %B %-d")
    except (ValueError, TypeError):
        return iso


def _pretty_time(hhmm: str) -> str:
    try:
        h, m = map(int, hhmm.split(":"))
        suffix = "a.m." if h < 12 else "p.m."
        h12 = h % 12
        if h12 == 0:
            h12 = 12
        if m == 0:
            return f"{h12} {suffix}"
        return f"{h12}:{m:02d} {suffix}"
    except (ValueError, TypeError):
        return hhmm
