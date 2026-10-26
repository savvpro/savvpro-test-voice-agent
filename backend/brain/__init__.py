"""
Voice assistant brain package.

Public surface:
    DialogueManager   — the rule-based state machine
    Session           — per-caller session object
    BrainResponse     — what the brain returns each turn
    State             — enumeration of dialogue states
    DM                — process-wide singleton DialogueManager
"""

from .state_machine import DialogueManager, Session, BrainResponse, State, DM
from .intents import classify, top_intent, Intent
from .slots import extract_all, extract_date, extract_time, extract_party_size, extract_phone, extract_name
from .restaurant import STORE, Booking

__all__ = [
    "DialogueManager", "Session", "BrainResponse", "State", "DM",
    "classify", "top_intent", "Intent",
    "extract_all", "extract_date", "extract_time", "extract_party_size", "extract_phone", "extract_name",
    "STORE", "Booking",
]
