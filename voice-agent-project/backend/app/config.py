"""Settings read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    )
    session_ttl_seconds: int = int(os.getenv("SESSION_TTL_SECONDS", "1800"))
    timezone: str = os.getenv("CLINIC_TIMEZONE", "Asia/Karachi")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
