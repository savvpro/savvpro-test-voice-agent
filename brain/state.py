from dataclasses import dataclass, field
from typing import Dict, Optional


GREETING = "GREETING"
COLLECTING = "COLLECTING"
CHECKING_AVAILABILITY = "CHECKING_AVAILABILITY"
CONFIRMING = "CONFIRMING"
BOOKED = "BOOKED"
GOODBYE = "GOODBYE"
CANCELLED = "CANCELLED"


@dataclass
class Session:
    current_state: str = GREETING
    slots: Dict[str, str] = field(default_factory=dict)
    pending_slot: Optional[str] = None
    awaiting_change_field: bool = False

    def copy(self) -> "Session":
        return Session(
            self.current_state,
            dict(self.slots),
            self.pending_slot,
            self.awaiting_change_field,
        )
