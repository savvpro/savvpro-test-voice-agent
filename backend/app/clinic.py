from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class Doctor:
    id: str
    name: str
    specialty: str


DOCTORS: tuple[Doctor, ...] = (
    Doctor("patel", "Dr. Anita Patel", "general practice"),
    Doctor("khan", "Dr. Omar Khan", "general practice"),
    Doctor("nguyen", "Dr. Linh Nguyen", "dermatology"),
    Doctor("garcia", "Dr. Maria Garcia", "pediatrics"),
)

SPECIALTY_SYNONYMS: dict[str, str] = {
    **dict.fromkeys(
        ["gp", "general", "family", "checkup", "check-up", "physical"], "general practice"
    ),
    **dict.fromkeys(["skin", "rash", "dermatologist", "dermatology", "acne"], "dermatology"),
    **dict.fromkeys(["child", "kid", "pediatrician", "pediatrics", "baby"], "pediatrics"),
}

OPEN = time(9, 0)
CLOSE = time(17, 0)
SLOT_MINUTES = 30
EMERGENCY_NUMBER = "911"
CLINIC_NAME = "Maple Street Clinic"


def doctor_by_id(id: str) -> Doctor | None:
    return next((d for d in DOCTORS if d.id == id), None)


def doctors_for(specialty: str) -> list[Doctor]:
    return [d for d in DOCTORS if d.specialty == specialty]
