import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Settings:
    database_path: str
    cors_origins: list[str]
    timezone: ZoneInfo


def get_settings() -> Settings:
    origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
    return Settings(
        database_path=os.environ.get("DATABASE_PATH", "clinic.db"),
        cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        timezone=ZoneInfo(os.environ.get("CLINIC_TIMEZONE", "America/New_York")),
    )
