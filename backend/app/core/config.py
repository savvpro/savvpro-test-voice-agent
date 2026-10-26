"""Application settings loaded from environment variables.

Uses pydantic-settings so every value can be overridden via env vars or a
.env file without touching code.  The ``get_settings`` helper caches the
result so the file is parsed at most once per process.
"""

from __future__ import annotations

import functools

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All runtime configuration for the REDELIVER backend."""

    # --- CORS ---
    cors_origins: str = "http://localhost:3000"

    # --- Logging ---
    log_level: str = "INFO"

    # --- Session ---
    session_ttl_minutes: int = 30

    # --- Attempt limits ---
    max_tracking_attempts: int = 3
    max_phone_attempts: int = 3
    max_silence_turns: int = 3
    max_unknown_turns: int = 5

    # --- Data ---
    data_dir: str = "data"

    # --- App meta ---
    app_env: str = "development"
    app_version: str = "1.0.0"

    # -- helpers --
    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return v.upper()

    @property
    def cors_origin_list(self) -> list[str]:
        """Split the comma-separated ``CORS_ORIGINS`` string into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance (parsed once per process)."""
    return Settings()
