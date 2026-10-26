"""FastAPI application for Tableline voice agent."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
from typing import Dict, Any, Optional

from .models import (
    ConversationTurnRequest,
    ConversationTurnResponse,
    ConversationState,
    BookingDetails,
    ReservationRecord,
)
from .dialogue_manager import DialogueManager
from .restaurant_service import RestaurantService

app = FastAPI(
    title="Tableline Voice Agent API",
    description="Deterministic restaurant reservation conversational assistant backend",
    version="1.0.0"
)

# Enable CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

restaurant_service = RestaurantService()
dialogue_manager = DialogueManager(restaurant_service=restaurant_service)


class StartConversationResponse(BaseModel):
    conversation_id: str
    state: ConversationState
    assistant_message: str
    booking_details: BookingDetails


class ResetConversationRequest(BaseModel):
    conversation_id: str


@app.get("/api/health")
def health_check():
    """Health endpoint for uptime and container health checks."""
    return {"status": "ok", "service": "Tableline Voice Agent Backend", "engine": "deterministic"}


@app.post("/api/conversation/start", response_model=StartConversationResponse)
def start_conversation():
    """Initializes a new reservation dialogue session."""
    conv_id = f"conv_{uuid.uuid4().hex[:8]}"
    session = dialogue_manager.get_or_create_session(conv_id)
    session.state = ConversationState.GREETING
    
    welcome_msg = (
        "Good evening, thank you for calling Tableline. "
        "I'm your reservation concierge. When would you like to join us, and for how many guests?"
    )
    
    return StartConversationResponse(
        conversation_id=conv_id,
        state=session.state,
        assistant_message=welcome_msg,
        booking_details=session.booking_details
    )


@app.post("/api/conversation/turn", response_model=ConversationTurnResponse)
def conversation_turn(req: ConversationTurnRequest):
    """Processes user voice/text utterance and returns assistant response and state."""
    if not req.conversation_id:
        raise HTTPException(status_code=400, detail="Missing conversation_id")
    if not req.message or not req.message.strip():
        session = dialogue_manager.get_or_create_session(req.conversation_id)
        return ConversationTurnResponse(
            conversation_id=req.conversation_id,
            state=session.state,
            assistant_message="I didn't quite hear that. Could you repeat that for me?",
            booking_details=session.booking_details
        )

    response = dialogue_manager.process_turn(req.conversation_id, req.message)
    return response


@app.post("/api/conversation/reset", response_model=StartConversationResponse)
def reset_conversation(req: ResetConversationRequest):
    """Resets active dialogue session back to clean initial state."""
    if not req.conversation_id:
        raise HTTPException(status_code=400, detail="Missing conversation_id")
    
    session = dialogue_manager.reset_session(req.conversation_id)
    session.state = ConversationState.GREETING
    return StartConversationResponse(
        conversation_id=req.conversation_id,
        state=session.state,
        assistant_message="Certainly, let's start over fresh. When would you like a table, and for how many guests?",
        booking_details=session.booking_details
    )


@app.get("/api/reservations/{reservation_id}", response_model=ReservationRecord)
def get_reservation(reservation_id: str):
    """Demonstration verification endpoint to inspect stored bookings."""
    rec = restaurant_service.get_reservation(reservation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Reservation reference not found")
    return rec
