"""Clinic scheduling rules."""

import os
import secrets
from datetime import date

DB_PATH = os.getenv("VA_DB", "voice_assistant.db")
CLINIC_NAME = "Children's Specialist Clinic"

WORKING_DAYS = (0, 1, 2, 3, 4)
DAILY_CAPACITY = 35
CONSULTATION_MINUTES = 14
OPEN_MIN = 9 * 60
CLOSE_MIN = OPEN_MIN + DAILY_CAPACITY * CONSULTATION_MINUTES
MAX_FAILS = 3
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_SENDER = os.getenv("SMTP_SENDER", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
STAFF_API_KEY = os.getenv("STAFF_API_KEY", "")
EMAIL_VERIFICATION_SECRET = os.getenv("EMAIL_VERIFICATION_SECRET") or secrets.token_hex(32)
CALL_STATE_ENCRYPTION_KEY = os.getenv("CALL_STATE_ENCRYPTION_KEY", "")


def is_working_day(day: date) -> bool:
    return day.weekday() in WORKING_DAYS


def generate_slots() -> list[dict[str, int]]:
    return [
        {
            "token": token,
            "start_min": OPEN_MIN + (token - 1) * CONSULTATION_MINUTES,
            "end_min": OPEN_MIN + token * CONSULTATION_MINUTES,
        }
        for token in range(1, DAILY_CAPACITY + 1)
    ]
