from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

PKT = ZoneInfo("Asia/Karachi")
SERVICES: dict[str, dict[str, Any]] = {
    "oil_change": {"name": "Oil Change", "minutes": 30},
    "tyre_rotation": {"name": "Tyre Rotation", "minutes": 30},
    "brake_inspection": {"name": "Brake Inspection", "minutes": 60},
}


def clock() -> datetime:
    return datetime.now(PKT)


def local_slot(day: str, at: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), time.fromisoformat(at), PKT)


def utc_naive(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


def from_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC).astimezone(PKT)


def next_open(day: date) -> date:
    while day.weekday() == 6:
        day += timedelta(days=1)
    return day


def describe(service: str, vehicle: str, start: datetime) -> str:
    at = start.strftime("%I:%M %p").lstrip("0").replace(":00", "")
    return f"{SERVICES[service]['name']} for your {vehicle.upper() if vehicle == 'suv' else 'car'}, {start.strftime('%A, %d %B')} at {at} PKT"


def validate_slot(service: str, start: datetime, now: datetime) -> str | None:
    if start.date() < now.date() or start <= now:
        return "That time is in the past. Which future date and time would you like?"
    if start.date() > now.date() + timedelta(days=14):
        return "We book up to 14 days ahead. Which date within the next two weeks works?"
    if start.weekday() == 6:
        return "We are closed on Sundays. Which Monday-to-Saturday date would you prefer?"
    if start.minute not in (0, 30):
        return "Appointments start on the hour or half hour. Which time would you prefer?"
    end = start + timedelta(minutes=SERVICES[service]["minutes"])
    if start.hour < 9 or end.date() != start.date() or end.time() > time(18):
        return f"We open at 9 AM and close at 6 PM. {SERVICES[service]['name']} takes {SERVICES[service]['minutes']} minutes and must finish by 6 PM. Which earlier time works?"
    return None
