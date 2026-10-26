"""Environment configuration and a replaceable clock. No network services required."""
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./voxdesk.db"
    business_timezone: str = "Asia/Karachi"
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.business_timezone)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv("VOXDESK_DATABASE_URL", cls.database_url),
            business_timezone=os.getenv("VOXDESK_TIMEZONE", cls.business_timezone),
            cors_origins=tuple(os.getenv("VOXDESK_CORS_ORIGINS", ",".join(cls.cors_origins)).split(",")),
        )
