"""Application configuration via pydantic-settings.

All env vars are defined here.  Import ``settings`` everywhere;
never call ``os.environ`` directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./dev.db",
        description="Async SQLAlchemy DB URL. Use asyncpg for Postgres.",
    )

    # Postgres individual parts (used by docker-compose / migrations)
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_user: str = Field(default="brightsmile")
    postgres_password: str = Field(default="brightsmile_dev_pw")
    postgres_db: str = Field(default="brightsmile")

    # ── App server ────────────────────────────────────────────────────────────
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    reload: bool = Field(default=False)
    log_level: Literal["debug", "info", "warning", "error"] = Field(default="info")
    environment: Literal["development", "production", "test"] = Field(default="development")

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins.",
    )

    # ── Clinic rules ─────────────────────────────────────────────────────────
    clinic_name: str = Field(default="BrightSmile Dental Clinic")
    clinic_open_hour: int = Field(default=9, ge=0, le=23)
    clinic_close_hour: int = Field(default=17, ge=0, le=23)
    clinic_slot_minutes: int = Field(default=30, ge=10, le=120)
    # 0=Mon … 5=Sat; Sunday (6) is always closed
    clinic_open_weekdays: list[int] = Field(
        default=[0, 1, 2, 3, 4, 5],
        description="Weekdays the clinic is open (0=Mon, 6=Sun).",
    )

    # ── Session store ─────────────────────────────────────────────────────────
    session_ttl_seconds: int = Field(default=300, ge=60)
    session_max_size: int = Field(default=1000, ge=10)

    # ── Voice pipeline ───────────────────────────────────────────────────────
    max_audio_bytes: int = Field(default=1_048_576)  # 1 MB
    max_text_chars: int = Field(default=500)
    max_turns: int = Field(default=40)
    max_concurrent_calls: int = Field(default=10, ge=1)
    call_idle_timeout_seconds: float = Field(default=30.0, ge=1.0)
    rate_limit_messages_per_second: float = Field(default=20.0, ge=0.5)

    # ── STT / TTS ─────────────────────────────────────────────────────────────
    stt_provider: str = Field(default="faster_whisper")
    tts_provider: str = Field(default="edge_tts")
    whisper_model: str = Field(default="base.en")
    whisper_device: str = Field(default="cpu")
    whisper_compute_type: str = Field(default="int8")
    tts_voice: str = Field(default="en-US-JennyNeural")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: object) -> object:
        """Allow a comma-separated string as well as a real list."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("clinic_open_weekdays", mode="before")
    @classmethod
    def parse_weekdays(cls, v: object) -> object:
        if isinstance(v, str):
            return [int(d.strip()) for d in v.split(",") if d.strip()]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()


# Module-level convenience alias
settings: Settings = get_settings()
