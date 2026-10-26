"""The brain: a state machine that decides what to ask next.

STATES:
  GREETING → COLLECT_DAY → COLLECT_TIME → COLLECT_PARTY_SIZE
  → COLLECT_NAME → CONFIRM → BOOKED

Any state can jump to CANCEL or GOODBYE.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

from .helpers import get_day, get_time, get_party_size, get_name, get_intent


class State(str, Enum):
    GREETING = "greeting"
    COLLECT_DAY = "collect_day"
    COLLECT_TIME = "collect_time"
    COLLECT_PARTY_SIZE = "collect_party_size"
    COLLECT_NAME = "collect_name"
    CONFIRM = "confirm"
    BOOKED = "booked"
    CANCEL = "cancel"
    GOODBYE = "goodbye"


@dataclass
class Session:
    """Everything we know about one conversation."""
    state: State = State.GREETING
    day: Optional[str] = None
    time: Optional[str] = None
    party_size: Optional[int] = None
    name: Optional[str] = None
    booking_id: Optional[str] = None


# Fake data: tables in the restaurant + existing bookings
TABLES = [
    {"id": "T1", "capacity": 2},
    {"id": "T2", "capacity": 2},
    {"id": "T3", "capacity": 4},
    {"id": "T4", "capacity": 4},
    {"id": "T5", "capacity": 6},
    {"id": "T6", "capacity": 8},
]
# Key: (day, time) → list of table ids already booked
BOOKINGS: dict[tuple, list] = {}


def find_free_table(day: str, time: str, size: int) -> Optional[str]:
    """Look for a free table that fits the party size."""
    booked_tables = BOOKINGS.get((day, time), [])
    for table in TABLES:
        if table["capacity"] >= size and table["id"] not in booked_tables:
            return table["id"]
    return None


def book_table(day: str, time: str, size: int) -> Optional[str]:
    """Reserve a table. Returns booking id or None if full."""
    table_id = find_free_table(day, time, size)
    if not table_id:
        return None
    BOOKINGS.setdefault((day, time), []).append(table_id)
    booking_id = f"BK{len(BOOKINGS):04d}"
    return booking_id


def handle(session: Session, text: str) -> tuple[str, Session, dict]:
    """Main entry point. Takes the caller's text, returns (reply, session, debug)."""
    intent = get_intent(text)
    debug = {"intent": intent, "entities": {}}

    # Global intents work in any state
    if intent == "cancel":
        session.state = State.CANCEL
        return "Your booking has been cancelled. Goodbye!", session, debug
    if intent == "goodbye":
        session.state = State.GOODBYE
        return "Thank you for calling. Goodbye!", session, debug
    if intent == "out_of_scope":
        return "I can help with that when you arrive! But right now, I just need to know what day you'd like to book.", session, debug

    # If the caller says "change X" during CONFIRM, handle it specially
    if session.state == State.CONFIRM and intent == "change":
        new_time = get_time(text)
        new_size = get_party_size(text)
        new_day = get_day(text)
        if new_day:
            session.day = new_day
            debug["entities"]["day"] = new_day
        if new_time:
            session.time = new_time
            debug["entities"]["time"] = new_time
        if new_size:
            session.party_size = new_size
            debug["entities"]["party_size"] = new_size
        return (
            f"Updated. To confirm: table for {session.party_size} on "
            f"{session.day} at {session.time} under {session.name}. Shall I book it?",
            session,
            debug,
        )

    # State machine — one branch per state
    if session.state == State.GREETING:
        session.state = State.COLLECT_DAY
        return "Welcome to Savv Restaurant! What day would you like to book?", session, debug

    if session.state == State.COLLECT_DAY:
        day = get_day(text)
        debug["entities"]["day"] = day
        if day:
            session.day = day
            session.state = State.COLLECT_TIME
            return f"{day}. What time would you like?", session, debug
        
        # NEW: Handle plural "weekdays" gracefully
        if "weekday" in text.lower() or "weekend" in text.lower():
            return "Please pick a specific day, like Monday or Friday, or say today / tomorrow.", session, debug
            
        return "Sorry, could you say a weekday, or today / tomorrow?", session, debug

    if session.state == State.COLLECT_TIME:
        time = get_time(text)
        debug["entities"]["time"] = time
        if time:
            session.time = time
            session.state = State.COLLECT_PARTY_SIZE
            return f"{time}. How many people?", session, debug
        return "Sorry, what time? For example 7 PM or 19:30.", session, debug

    if session.state == State.COLLECT_PARTY_SIZE:
        size = get_party_size(text)
        debug["entities"]["party_size"] = size
        if size and 1 <= size <= 8:
            session.party_size = size
            session.state = State.COLLECT_NAME
            return f"Table for {size}. What name should I put it under?", session, debug
        if size and size > 8:
            return "For 8+ guests, please call our events line. How many instead?", session, debug
        return "How many people? Just a number is fine.", session, debug

    if session.state == State.COLLECT_NAME:
        name = get_name(text)
        debug["entities"]["name"] = name
        if name:
            session.name = name
            # Check availability before confirming
            if not find_free_table(session.day, session.time, session.party_size):
                session.state = State.COLLECT_TIME
                return (
                    f"Sorry, we're full at {session.time} on {session.day}. "
                    "What other time works?",
                    session,
                    debug,
                )
            session.state = State.CONFIRM
            return (
                f"To confirm: table for {session.party_size} on {session.day} "
                f"at {session.time} under {session.name}. Shall I book it?",
                session,
                debug,
            )
        return "Sorry, what name should I put it under?", session, debug

    if session.state == State.CONFIRM:
        if intent == "yes":
            booking_id = book_table(session.day, session.time, session.party_size)
            if booking_id:
                session.booking_id = booking_id
                session.state = State.BOOKED
                return (
                    f"Booked! Table for {session.party_size} on {session.day} at "
                    f"{session.time}. Booking id {booking_id}. Goodbye!",
                    session,
                    debug,
                )
            session.state = State.COLLECT_TIME
            return "That slot just filled up. What other time works?", session, debug
        if intent == "no":
            session.state = State.COLLECT_DAY
            return "No problem. What day would you like?", session, debug
        return "Just to confirm — should I book it? Yes or no.", session, debug

    if session.state == State.BOOKED:
        return "Your booking is confirmed. Is there anything else?", session, debug

    return "I'm not sure I understood. Could you say that again?", session, debug