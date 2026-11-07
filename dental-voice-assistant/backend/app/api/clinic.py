"""GET /clinic — expose clinic rules and configuration."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/clinic", tags=["clinic"])


class ClinicInfo(BaseModel):
    name: str
    open_hour: int
    close_hour: int
    slot_minutes: int
    open_weekdays: list[int]
    services: list[str]


_SERVICES = [
    "cleaning",
    "checkup",
    "filling",
    "whitening",
    "root canal",
    "braces consultation",
]


@router.get("", response_model=ClinicInfo, summary="Clinic configuration")
async def clinic_info() -> ClinicInfo:
    """Return clinic rules (open hours, slot length, services)."""
    return ClinicInfo(
        name=settings.clinic_name,
        open_hour=settings.clinic_open_hour,
        close_hour=settings.clinic_close_hour,
        slot_minutes=settings.clinic_slot_minutes,
        open_weekdays=settings.clinic_open_weekdays,
        services=_SERVICES,
    )
