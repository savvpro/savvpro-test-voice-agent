"""Deterministic Dialogue Manager for Tableline voice agent.

Maintains conversation state machine, handles field corrections, invalidates stale availability,
suggests alternatives, and enforces explicit booking confirmation.
"""

from typing import Dict, Any, Optional, Tuple, List
import datetime
from .models import (
    ConversationState,
    BookingDetails,
    ConversationTurnResponse,
    BookingStatus,
)
from .parser import DeterministicParser
from .restaurant_service import RestaurantService


class DialogueSession:
    def __init__(self, conversation_id: str, parser: DeterministicParser, restaurant_service: RestaurantService):
        self.conversation_id = conversation_id
        self.state = ConversationState.IDLE
        self.booking_details = BookingDetails()
        self.parser = parser
        self.restaurant_service = restaurant_service
        self.suggested_alternatives: List[str] = []
        self.is_confirmed: bool = False
        self.reservation_reference: Optional[str] = None
        self.last_offered_time: Optional[str] = None

    def reset(self):
        self.state = ConversationState.IDLE
        self.booking_details = BookingDetails()
        self.suggested_alternatives = []
        self.is_confirmed = False
        self.reservation_reference = None
        self.last_offered_time = None


class DialogueManager:
    def __init__(self, restaurant_service: Optional[RestaurantService] = None, reference_date: Optional[datetime.date] = None):
        self.restaurant_service = restaurant_service or RestaurantService()
        self.parser = DeterministicParser(reference_date=reference_date)
        self.sessions: Dict[str, DialogueSession] = {}

    def get_or_create_session(self, conversation_id: str) -> DialogueSession:
        if conversation_id not in self.sessions:
            self.sessions[conversation_id] = DialogueSession(
                conversation_id=conversation_id,
                parser=self.parser,
                restaurant_service=self.restaurant_service
            )
        return self.sessions[conversation_id]

    def reset_session(self, conversation_id: str) -> DialogueSession:
        session = self.get_or_create_session(conversation_id)
        session.reset()
        return session

    def process_turn(self, conversation_id: str, utterance: str) -> ConversationTurnResponse:
        session = self.get_or_create_session(conversation_id)
        parsed = self.parser.parse_utterance(utterance)

        # 1. Global Commands: RESTART / RESET
        if parsed["intent"] == "RESTART":
            session.reset()
            return ConversationTurnResponse(
                conversation_id=conversation_id,
                state=ConversationState.GREETING,
                assistant_message="Certainly, let's start over. What date would you like to reserve a table for, and for how many guests?",
                booking_details=session.booking_details
            )

        # 2. Global Commands: CANCEL
        if parsed["intent"] == "CANCEL":
            session.state = ConversationState.CANCELLED
            session.is_confirmed = False
            session.reservation_reference = None
            return ConversationTurnResponse(
                conversation_id=conversation_id,
                state=ConversationState.CANCELLED,
                assistant_message="I've cancelled the reservation request. If you need anything else, just let me know.",
                booking_details=session.booking_details
            )

        # 3. Already Confirmed Idempotency Check
        if session.is_confirmed and session.reservation_reference:
            if parsed["intent"] == "CONFIRM":
                return ConversationTurnResponse(
                    conversation_id=conversation_id,
                    state=ConversationState.CONFIRMED,
                    assistant_message=f"Your reservation is already confirmed under reference {session.reservation_reference}. We look forward to seeing you!",
                    booking_details=session.booking_details,
                    is_confirmed=True,
                    reservation_reference=session.reservation_reference
                )
            elif not (parsed["date"] or parsed["time"] or parsed["guests"]):
                return ConversationTurnResponse(
                    conversation_id=conversation_id,
                    state=ConversationState.CONFIRMED,
                    assistant_message=f"Your table is confirmed with reference {session.reservation_reference}. If you'd like to make a new booking, just say start over.",
                    booking_details=session.booking_details,
                    is_confirmed=True,
                    reservation_reference=session.reservation_reference
                )

        # 4. Handle Ambiguous Date
        if parsed["is_date_ambiguous"]:
            return ConversationTurnResponse(
                conversation_id=conversation_id,
                state=session.state if session.state != ConversationState.IDLE else ConversationState.COLLECTING_DETAILS,
                assistant_message="I couldn't quite catch a valid future date. Could you please specify which date or day of the week you have in mind?",
                booking_details=session.booking_details
            )

        # 5. Entity Updates & Corrections
        details_updated = False
        correction_noted = []

        if parsed["guests"] is not None:
            if parsed["guests"] < 1:
                return ConversationTurnResponse(
                    conversation_id=conversation_id,
                    state=session.state,
                    assistant_message="A reservation requires at least one guest. How many people will be dining with us?",
                    booking_details=session.booking_details
                )
            if parsed["guests"] > 12:
                return ConversationTurnResponse(
                    conversation_id=conversation_id,
                    state=session.state,
                    assistant_message="For parties larger than 12 guests, our private dining manager handles bookings directly. Could we arrange a table for 12 or fewer today?",
                    booking_details=session.booking_details
                )
            if session.booking_details.guests != parsed["guests"]:
                session.booking_details.guests = parsed["guests"]
                details_updated = True
                correction_noted.append(f"{parsed['guests']} guests")

        if parsed["date"] is not None:
            if session.booking_details.date != parsed["date"]:
                session.booking_details.date = parsed["date"]
                details_updated = True
                correction_noted.append(f"date {parsed['date']}")

        if parsed["time"] is not None:
            if session.booking_details.time != parsed["time"]:
                session.booking_details.time = parsed["time"]
                details_updated = True
                correction_noted.append(f"{parsed['time']}")

        if parsed["customer_name"] is not None:
            session.booking_details.customer_name = parsed["customer_name"]

        # If details changed after availability or confirmation, invalidate stale confirmation state!
        if details_updated and session.state in (ConversationState.AWAITING_CONFIRMATION, ConversationState.CONFIRMED, ConversationState.OFFERING_ALTERNATIVES):
            session.is_confirmed = False
            session.reservation_reference = None
            session.suggested_alternatives = []
            session.state = ConversationState.COLLECTING_DETAILS

        # 6. Check state: AWAITING_CONFIRMATION
        if session.state == ConversationState.AWAITING_CONFIRMATION:
            if parsed["intent"] == "CONFIRM":
                # Final availability re-validation before booking!
                b = session.booking_details
                is_avail, _, _ = self.restaurant_service.check_availability(b.date, b.time, b.guests)
                if not is_avail:
                    session.state = ConversationState.OFFERING_ALTERNATIVES
                    alts = self.restaurant_service.get_available_alternatives(b.date, b.time, b.guests)
                    session.suggested_alternatives = alts
                    alt_text = f"such as {', '.join(alts)}" if alts else "on that evening"
                    return ConversationTurnResponse(
                        conversation_id=conversation_id,
                        state=ConversationState.OFFERING_ALTERNATIVES,
                        assistant_message=f"I apologize, but that slot just became unavailable. We have openings {alt_text}. Would one of those work for you?",
                        booking_details=session.booking_details,
                        suggested_alternatives=alts
                    )

                # Create real fictional booking
                record = self.restaurant_service.create_reservation(
                    date_str=b.date,
                    time_str=b.time,
                    guests=b.guests,
                    customer_name=b.customer_name or "Guest"
                )
                session.state = ConversationState.CONFIRMED
                session.is_confirmed = True
                session.reservation_reference = record.reservation_id

                return ConversationTurnResponse(
                    conversation_id=conversation_id,
                    state=ConversationState.CONFIRMED,
                    assistant_message=f"Wonderful! Your table for {b.guests} on {b.date} at {b.time} is officially confirmed under reference {record.reservation_id}. We look forward to hosting you!",
                    booking_details=session.booking_details,
                    is_confirmed=True,
                    reservation_reference=record.reservation_id
                )
            elif parsed["intent"] == "REJECT":
                session.state = ConversationState.COLLECTING_DETAILS
                return ConversationTurnResponse(
                    conversation_id=conversation_id,
                    state=ConversationState.COLLECTING_DETAILS,
                    assistant_message="No problem at all. Which detail would you like to change — the date, time, or number of guests?",
                    booking_details=session.booking_details
                )

        # 7. Check if we need more information (Date, Guests, Time)
        missing = []
        if not session.booking_details.date:
            missing.append("date")
        if not session.booking_details.guests:
            missing.append("guests")
        if not session.booking_details.time:
            missing.append("time")

        prefix = ""
        if parsed["is_correction"] and correction_noted:
            prefix = f"Of course, I've updated that to {', '.join(correction_noted)}. "
        elif details_updated and session.state != ConversationState.IDLE:
            prefix = f"Got it, updated to {', '.join(correction_noted)}. "

        if missing:
            session.state = ConversationState.COLLECTING_DETAILS
            if "date" in missing and "guests" in missing:
                msg = prefix + "Welcome to Tableline. When would you like to join us, and how many guests will be in your party?"
            elif "date" in missing:
                msg = prefix + "What date would you like to book the table for?"
            elif "guests" in missing:
                msg = prefix + "How many guests will be dining with you?"
            elif "time" in missing:
                msg = prefix + f"What time would you prefer on {session.booking_details.date}? We are open for dinner from 5:00 PM to 9:30 PM."
            else:
                msg = prefix + "Could you please specify your preferred dining time?"

            return ConversationTurnResponse(
                conversation_id=conversation_id,
                state=ConversationState.COLLECTING_DETAILS,
                assistant_message=msg,
                booking_details=session.booking_details
            )

        # 8. All details collected -> Check Availability!
        b = session.booking_details
        is_avail, remaining, alts = self.restaurant_service.check_availability(b.date, b.time, b.guests)

        if not is_avail:
            session.state = ConversationState.OFFERING_ALTERNATIVES
            session.suggested_alternatives = alts
            alt_list = ", ".join(alts) if alts else "none on this date"
            alt_prompt = f"However, we have tables open at {alt_list}. Would any of those suit your party?" if alts else "Would you like to try another date?"
            
            reply = f"{prefix}I checked our availability for {b.guests} guests on {b.date} at {b.time}, but that slot is currently fully booked. {alt_prompt}"
            return ConversationTurnResponse(
                conversation_id=conversation_id,
                state=ConversationState.OFFERING_ALTERNATIVES,
                assistant_message=reply,
                booking_details=session.booking_details,
                suggested_alternatives=alts
            )

        # 9. Slot is available -> Present summary and transition to AWAITING_CONFIRMATION
        session.state = ConversationState.AWAITING_CONFIRMATION
        session.suggested_alternatives = []
        name_str = f" for {b.customer_name}" if b.customer_name else ""
        
        reply = (
            f"{prefix}Good news! We have a table available on {b.date} at {b.time} for {b.guests} guests{name_str}. "
            f"Would you like me to go ahead and confirm this reservation?"
        )

        return ConversationTurnResponse(
            conversation_id=conversation_id,
            state=ConversationState.AWAITING_CONFIRMATION,
            assistant_message=reply,
            booking_details=session.booking_details
        )
