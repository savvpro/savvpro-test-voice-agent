"""State and intent definitions for the conversation finite state machine."""

from enum import Enum


class ConversationState(Enum):
    """States in the restaurant reservation conversation FSM.

    The conversation follows this general flow:
    GREETING → ASK_DATE → ASK_TIME → ASK_PARTY_SIZE → CONFIRM → COMPLETED

    Users may jump forward if they provide multiple pieces of information
    at once, and may go back to correct previously provided information.
    """

    GREETING = "greeting"
    ASK_DATE = "ask_date"
    ASK_TIME = "ask_time"
    ASK_PARTY_SIZE = "ask_party_size"
    CONFIRM = "confirm"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Intent(Enum):
    """Recognised user intents, detected by keyword / regex matching."""

    GREETING = "greeting"
    PROVIDE_INFO = "provide_info"
    CONFIRM = "confirm"
    DENY = "deny"
    CANCEL = "cancel"
    RESTART = "restart"
    CHANGE_DATE = "change_date"
    CHANGE_TIME = "change_time"
    CHANGE_PARTY_SIZE = "change_party_size"
    HELP = "help"
    UNKNOWN = "unknown"
