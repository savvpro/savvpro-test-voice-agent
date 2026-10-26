"""Current time in the clinic's timezone."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def clinic_now() -> datetime:
    """Naive datetime in clinic-local time (the DB stores naive clinic-local times)."""
    tz = ZoneInfo(get_settings().clinic_timezone)
    return datetime.now(tz).replace(tzinfo=None)
