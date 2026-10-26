"""Everything the dialogue knows about one call."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel

from app.dialogue.states import State
from app.nlu.entities import TimeOfDay

Task = Literal["book", "reschedule", "cancel"]


class SlotOption(BaseModel):
    slot_id: int
    start: dt.datetime
    doctor: str
    department: str


class FoundAppointment(BaseModel):
    booking_ref: str
    slot_id: int
    start: dt.datetime
    doctor: str
    department: str
    patient_name: str


class Frame(BaseModel):
    state: State = State.GREETING
    task: Task | None = None

    department: str | None = None
    doctor: str | None = None
    date: dt.date | None = None
    time: dt.time | None = None
    time_of_day: TimeOfDay | None = None
    patient_name: str | None = None
    phone: str | None = None
    booking_ref: str | None = None

    candidate_slots: list[SlotOption] = []
    chosen_slot: SlotOption | None = None
    appointment: FoundAppointment | None = None  # existing booking (reschedule/cancel)

    last_prompt: str = ""
    expected_slot: str | None = None
    fail_count: int = 0
    silence_count: int = 0

    def clear_selection(self) -> None:
        self.candidate_slots = []
        self.chosen_slot = None

    def reset_task(self) -> None:
        """Forget the current task and its slots; keep conversation bookkeeping."""
        keep = {"state", "last_prompt", "expected_slot", "fail_count", "silence_count"}
        for name, field in Frame.model_fields.items():
            if name not in keep:
                setattr(self, name, field.get_default(call_default_factory=True))
