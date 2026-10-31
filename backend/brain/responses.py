"""
Response template builder.
All agent speech is generated here — FSM logic never builds strings directly.
"""

from datetime import datetime


# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt_date(date_str: str) -> str:
    """'2026-11-03' → 'Tuesday, November 3rd'"""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        day = d.day
        suffix = (
            "th" if 11 <= day <= 13
            else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        )
        return d.strftime(f"%A, %B {day}{suffix}")
    except Exception:
        return date_str


def _fmt_time(time_str: str) -> str:
    """'14:00' → '2:00 pm'"""
    try:
        t = datetime.strptime(time_str, "%H:%M")
        return t.strftime("%I:%M %p").lstrip("0").lower()
    except Exception:
        return time_str


# ── Templates ─────────────────────────────────────────────────────────────────

def greeting() -> str:
    return (
        "Hello! Welcome to City Dental Clinic. "
        "I can help you book, reschedule, or cancel an appointment. "
        "What would you like to do?"
    )


def ask_name() -> str:
    return "Could I please get your name?"


def ask_doctor() -> str:
    return (
        "Do you have a preferred doctor? "
        "We have Dr. Khan, Dr. Smith, Dr. Patel, and Dr. Ali. "
        "Or I can find the first available."
    )


def doctor_not_found(doctor: str) -> str:
    return (
        f"I'm sorry, {doctor} is not at our clinic. "
        "We have Dr. Khan, Dr. Smith, Dr. Patel, and Dr. Ali, or I can book with anyone available. "
        "Which would you prefer?"
    )


def ask_date() -> str:
    return "What date works best for you?"


def ask_time() -> str:
    return "And what time of day do you prefer?"


def ask_reason() -> str:
    return "What's the reason for your visit? You can skip this if you'd prefer."


def confirm_summary(slots: dict) -> str:
    name      = slots.get("name", "?")
    doctor    = slots.get("doctor", "any available doctor")
    date_str  = _fmt_date(slots.get("date", "?"))
    time_str  = _fmt_time(slots.get("time", "?"))
    reason    = slots.get("reason")
    reason_part = f" for {reason}" if reason else ""
    return (
        f"Let me confirm: appointment for {name}, "
        f"with {doctor}, on {date_str} at {time_str}{reason_part}. "
        "Does that all sound correct?"
    )


def booking_confirmed(slots: dict) -> str:
    name     = slots.get("name", "you")
    date_str = _fmt_date(slots.get("date", "?"))
    time_str = _fmt_time(slots.get("time", "?"))
    doctor   = slots.get("doctor", "your doctor")
    return (
        f"Perfect! You're all booked, {name}. "
        f"We'll see you on {date_str} at {time_str} with {doctor}. "
        "Have a great day!"
    )


def slot_unavailable(alternatives: list[dict]) -> str:
    if not alternatives:
        return (
            "Unfortunately that slot isn't available and I couldn't find any alternatives. "
            "Please call back during office hours."
        )
    alt      = alternatives[0]
    date_str = _fmt_date(alt["date"])
    time_str = _fmt_time(alt["time"])
    return (
        f"Unfortunately that slot isn't available. "
        f"The next opening I have is {date_str} at {time_str}. "
        "Would that work for you?"
    )


def correction_acknowledged() -> str:
    return "Of course, I've updated that."


def reschedule_ask_name() -> str:
    return "Sure, I can help you reschedule. Could I get your name so I can find your booking?"


def cancel_ask_name() -> str:
    return "Of course. Could I get your name so I can locate your appointment?"


def cancel_confirmed(name: str) -> str:
    return f"Done, {name}. Your appointment has been cancelled. Have a great day!"


def unclear_first() -> str:
    return "Sorry, I didn't quite catch that. Could you say it again?"


def unclear_second() -> str:
    return "I'm having a little trouble understanding. Could you rephrase that?"


def unclear_third() -> str:
    return (
        "I'm sorry, I'm having difficulty understanding. "
        "Let me connect you with a staff member. Goodbye!"
    )


def goodbye() -> str:
    return "Thank you for calling City Dental Clinic. Have a wonderful day! Goodbye!"


def past_date() -> str:
    return "That date has already passed. Could you pick a future date?"


def invalid_time() -> str:
    return "Sorry, I didn't catch a valid time. Could you say something like '3pm' or 'morning'?"

