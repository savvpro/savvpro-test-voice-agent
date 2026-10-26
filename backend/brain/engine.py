"""Dialog engine — the brain of the voice assistant.

Implements a finite-state-machine that drives the conversation.
The engine:
    1. Receives user text
    2. Classifies intents (rule-based)
    3. Extracts entities (rule-based)
    4. Transitions state
    5. Generates a response

NO AI/LLM is used for any decision-making.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Dict, Optional, Tuple
from uuid import uuid4

from brain.intents import Intent, classify
from brain.entities import extract_all
from models.booking import Booking, BookingStatus
from models.conversation import Conversation, ConversationState
from services.booking import BookingService
import config

logger = logging.getLogger(__name__)


class DialogEngine:
    """Stateful dialog engine for restaurant booking conversations."""

    def __init__(self) -> None:
        self._conversations: Dict[str, Conversation] = {}
        self._booking_service = BookingService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_conversation(self) -> Tuple[str, str, dict]:
        """Start a new conversation and return (conversation_id, greeting, state_info)."""
        conv_id = uuid4().hex[:12]
        conv = Conversation(id=conv_id)
        self._conversations[conv_id] = conv

        greeting = (
            f"Welcome to {config.RESTAURANT_NAME}! "
            "I can help you book a table. "
            "When would you like to dine with us?"
        )
        conv.state = ConversationState.ASK_DATE
        conv.add_turn("assistant", greeting)

        return conv_id, greeting, self._state_info(conv)

    def process(self, conv_id: str, user_text: str) -> Tuple[str, dict]:
        """Process user input and return (response, state_info).

        Raises KeyError if conv_id is not found.
        """
        conv = self._conversations[conv_id]

        # Classify intents and extract entities
        intents = classify(user_text)
        entities = extract_all(user_text)

        conv.add_turn("user", user_text, extracted={
            "intents": [i.value for i in intents],
            "entities": {k: str(v) for k, v in entities.items() if v is not None},
        })

        logger.info(
            "conv=%s state=%s intents=%s entities=%s",
            conv_id, conv.state.value, intents, entities,
        )

        # Handle global intents first
        response = self._handle_global_intents(conv, intents)
        if response:
            conv.add_turn("assistant", response)
            return response, self._state_info(conv)

        # Fill any entities regardless of current state (multi-slot)
        self._fill_slots(conv, entities)

        # State-specific transitions
        response = self._transition(conv, intents, entities)
        conv.add_turn("assistant", response)
        return response, self._state_info(conv)

    def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        """Retrieve a conversation by ID."""
        return self._conversations.get(conv_id)

    # ------------------------------------------------------------------
    # Global intents (always checked first)
    # ------------------------------------------------------------------

    def _handle_global_intents(
        self, conv: Conversation, intents: list[Intent]
    ) -> Optional[str]:
        """Handle intents that can fire from any state."""

        if Intent.CANCEL in intents:
            conv.booking.status = BookingStatus.CANCELLED
            conv.state = ConversationState.CANCELLED
            return (
                "No problem — I've cancelled your reservation request. "
                "If you'd like to book in the future, just give us a call. Goodbye!"
            )

        if Intent.HELP in intents:
            return (
                f"I can help you reserve a table at {config.RESTAURANT_NAME}. "
                f"We're open from {config.OPENING_HOUR}:00 to {config.CLOSING_HOUR}:00, "
                f"and can seat up to {config.MAX_PARTY_SIZE} guests. "
                "Just tell me the date, time, and party size and I'll check availability."
            )

        # Greeting handling: respond with a friendly welcome ONLY if the
        # message is a pure greeting with no booking-related entities.
        # If the user says "hello, book for tomorrow at 4pm" we fall through
        # so that slot-filling can capture the date/time.
        if Intent.GREETING in intents and conv.state == ConversationState.ASK_DATE:
            # Check if there are any entity-bearing intents alongside the greeting
            entity_intents = {
                Intent.PROVIDE_DATE, Intent.PROVIDE_TIME,
                Intent.PROVIDE_PARTY_SIZE, Intent.PROVIDE_NAME,
                Intent.PROVIDE_CONTACT, Intent.BOOK,
            }
            if not entity_intents.intersection(intents):
                return (
                    f"Hello! Welcome to {config.RESTAURANT_NAME}. "
                    "I'd love to help you book a table. "
                    "What date would you like to reserve?"
                )

        if conv.state in (ConversationState.GOODBYE, ConversationState.CANCELLED):
            if Intent.GREETING in intents or Intent.BOOK in intents:
                # Restart
                conv.booking = Booking()
                conv.state = ConversationState.ASK_DATE
                conv.modification_count = 0
                return (
                    f"Welcome back! Let's book a new table at {config.RESTAURANT_NAME}. "
                    "What date works for you?"
                )
            return "Goodbye! Call us anytime to make a reservation."

        return None

    # ------------------------------------------------------------------
    # Slot filling
    # ------------------------------------------------------------------

    def _fill_slots(self, conv: Conversation, entities: dict) -> None:
        """Fill booking slots from extracted entities."""
        booking = conv.booking

        if entities.get("date") and entities["date"] != booking.date:
            if booking.date is not None:
                conv.modification_count += 1
            booking.date = entities["date"]

        if entities.get("time") and entities["time"] != booking.time:
            if booking.time is not None:
                conv.modification_count += 1
            booking.time = entities["time"]

        if entities.get("party_size") and entities["party_size"] != booking.party_size:
            if booking.party_size is not None:
                conv.modification_count += 1
            booking.party_size = entities["party_size"]

        if entities.get("name"):
            booking.guest_name = entities["name"]

        if entities.get("contact"):
            booking.contact = entities["contact"]

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _transition(
        self, conv: Conversation, intents: list[Intent], entities: dict
    ) -> str:
        """Transition the state machine and return the response."""
        booking = conv.booking

        # Handle change intent — re-ask the relevant question
        if Intent.CHANGE in intents:
            return self._handle_change(conv, entities)

        # CONFIRM state — user must say yes or no
        if conv.state == ConversationState.CONFIRM:
            return self._handle_confirmation(conv, intents)

        # SUGGEST_ALTERNATIVE — user picks or rejects
        if conv.state == ConversationState.SUGGEST_ALTERNATIVE:
            if Intent.CONFIRM in intents:
                return self._finalize_booking(conv)
            elif Intent.DENY in intents:
                conv.state = ConversationState.ASK_DATE
                return "Alright, let's try different options. What date would you prefer?"
            return "Would you like me to book that alternative slot? Say yes or no."

        # BOOKED — already done
        if conv.state == ConversationState.BOOKED:
            conv.state = ConversationState.GOODBYE
            return (
                "Your table is already booked! "
                "Is there anything else I can help with, or shall we say goodbye?"
            )

        # Validate and advance through states
        return self._advance(conv)

    def _advance(self, conv: Conversation) -> str:
        """Advance through the slot-filling states."""
        booking = conv.booking

        # Validate date
        if booking.date is not None:
            if booking.date < date.today():
                booking.date = None
                conv.state = ConversationState.ASK_DATE
                return (
                    "That date has already passed. "
                    "Could you give me a future date for your reservation?"
                )

        # Validate time
        if booking.time is not None:
            hour = booking.time.hour
            if hour < config.OPENING_HOUR or hour >= config.CLOSING_HOUR:
                booking.time = None
                conv.state = ConversationState.ASK_TIME
                return (
                    f"I'm sorry, we're only open from "
                    f"{config.OPENING_HOUR}:00 to {config.CLOSING_HOUR}:00. "
                    "What time would work for you?"
                )

        # Validate party size
        if booking.party_size is not None:
            if booking.party_size < 1:
                booking.party_size = None
                conv.state = ConversationState.ASK_PARTY_SIZE
                return "Please tell me a valid number of guests."
            if booking.party_size > config.MAX_PARTY_SIZE:
                booking.party_size = None
                conv.state = ConversationState.ASK_PARTY_SIZE
                return (
                    f"I'm sorry, we can only seat up to {config.MAX_PARTY_SIZE} guests. "
                    "How many people will be joining?"
                )

        # Determine what to ask next
        if booking.date is None:
            conv.state = ConversationState.ASK_DATE
            return "What date would you like to reserve?"

        if booking.time is None:
            conv.state = ConversationState.ASK_TIME
            date_str = booking.date.strftime("%A, %B %d")
            return f"Great, {date_str}! What time would you like your table?"

        if booking.party_size is None:
            conv.state = ConversationState.ASK_PARTY_SIZE
            return "And how many guests will be dining?"

        if booking.guest_name is None:
            conv.state = ConversationState.ASK_NAME
            return "Wonderful! May I have a name for the reservation?"

        # All slots filled — check availability
        return self._check_and_confirm(conv)

    def _check_and_confirm(self, conv: Conversation) -> str:
        """Check availability and present confirmation."""
        booking = conv.booking
        available = self._booking_service.check_availability(
            booking.date, booking.time, booking.party_size
        )

        if available:
            conv.state = ConversationState.CONFIRM
            return (
                f"Let me confirm your reservation:\n"
                f"• Date: {booking.date.strftime('%A, %B %d, %Y')}\n"
                f"• Time: {booking.time.strftime('%I:%M %p')}\n"
                f"• Party size: {booking.party_size}\n"
                f"• Name: {booking.guest_name}\n"
                "Shall I go ahead and book this?"
            )
        else:
            alt = self._booking_service.find_alternative(
                booking.date, booking.time, booking.party_size
            )
            if alt:
                alt_date, alt_time = alt
                conv.booking.date = alt_date
                conv.booking.time = alt_time
                conv.state = ConversationState.SUGGEST_ALTERNATIVE
                return (
                    f"I'm sorry, that slot isn't available. "
                    f"How about {alt_date.strftime('%A, %B %d')} "
                    f"at {alt_time.strftime('%I:%M %p')} instead?"
                )
            else:
                conv.state = ConversationState.ASK_DATE
                booking.date = None
                booking.time = None
                return (
                    "Unfortunately, we don't have availability around that time. "
                    "Would you like to try a different date?"
                )

    def _handle_confirmation(self, conv: Conversation, intents: list[Intent]) -> str:
        """Handle yes/no at the confirmation step."""
        if Intent.CONFIRM in intents:
            return self._finalize_booking(conv)
        elif Intent.DENY in intents:
            conv.state = ConversationState.ASK_DATE
            return "No problem. Let's start over — what date would you prefer?"
        return (
            "I just need a yes or no to confirm the booking. "
            "Shall I go ahead and reserve that table?"
        )

    def _finalize_booking(self, conv: Conversation) -> str:
        """Mark booking as confirmed."""
        conv.booking.status = BookingStatus.CONFIRMED
        self._booking_service.save_booking(conv.booking)
        conv.state = ConversationState.BOOKED

        return (
            f"Excellent! Your table is booked! 🎉\n"
            f"Booking reference: #{conv.booking.id}\n"
            f"• {conv.booking.date.strftime('%A, %B %d, %Y')} "
            f"at {conv.booking.time.strftime('%I:%M %p')}\n"
            f"• Party of {conv.booking.party_size} under {conv.booking.guest_name}\n"
            f"Thank you for choosing {config.RESTAURANT_NAME}! See you soon."
        )

    def _handle_change(self, conv: Conversation, entities: dict) -> str:
        """Handle modification requests."""
        conv.modification_count += 1
        text_lower = " ".join([t.text.lower() for t in conv.turns[-2:]])

        if "date" in text_lower or "day" in text_lower or entities.get("date"):
            conv.booking.date = entities.get("date")
            conv.state = ConversationState.ASK_DATE
            if conv.booking.date:
                return self._advance(conv)
            return "Sure, what date would you like instead?"

        if "time" in text_lower or entities.get("time"):
            conv.booking.time = entities.get("time")
            conv.state = ConversationState.ASK_TIME
            if conv.booking.time:
                return self._advance(conv)
            return "Of course, what time works better for you?"

        if "people" in text_lower or "party" in text_lower or "size" in text_lower \
                or "guests" in text_lower or entities.get("party_size"):
            conv.booking.party_size = entities.get("party_size")
            conv.state = ConversationState.ASK_PARTY_SIZE
            if conv.booking.party_size:
                return self._advance(conv)
            return "No problem, how many guests will there be?"

        if "name" in text_lower or entities.get("name"):
            conv.booking.guest_name = entities.get("name")
            conv.state = ConversationState.ASK_NAME
            if conv.booking.guest_name:
                return self._advance(conv)
            return "Sure, what name should I put the reservation under?"

        # Generic change — ask what to change
        return (
            "What would you like to change? "
            "I can update the date, time, party size, or name."
        )

    # ------------------------------------------------------------------
    # State info for frontend
    # ------------------------------------------------------------------

    def _state_info(self, conv: Conversation) -> dict:
        """Build state info dict for the frontend."""
        last_decision = None
        for turn in reversed(conv.turns):
            if turn.role == "user" and turn.extracted:
                last_decision = turn.extracted
                break

        return {
            "conversation_id": conv.id,
            "state": conv.state.value,
            "last_decision": last_decision,
            "booking": {
                "id": conv.booking.id,
                "guest_name": conv.booking.guest_name,
                "date": conv.booking.date.isoformat() if conv.booking.date else None,
                "time": conv.booking.time.isoformat() if conv.booking.time else None,
                "party_size": conv.booking.party_size,
                "contact": conv.booking.contact,
                "status": conv.booking.status.value,
            },
            "turn_count": conv.turn_count,
            "modifications": conv.modification_count,
        }
