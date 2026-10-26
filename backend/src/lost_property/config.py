import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

env_file = os.getenv("ENV_FILE")
if env_file:
    load_dotenv(env_file, override=False)
else:
    # Both repository-root and backend-directory launch commands are supported.
    for candidate in (
        Path.cwd() / ".env",
        Path.cwd() / "backend" / ".env",
        Path.cwd().parent / ".env",
    ):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            break


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""), repr=False)
    audio_max_bytes: int = 8 * 1024 * 1024
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./riverside.db")
    )
    allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://127.0.0.1:8000").split(",")
        )
    )
    secure_cookies: bool = field(
        default_factory=lambda: os.getenv("SECURE_COOKIES", "false").lower() == "true"
    )
    idle_seconds: int = 1800
    absolute_seconds: int = 86400
    session_limit: int = 5
    turn_limit: int = 30
    static_directory: str | None = field(default_factory=lambda: os.getenv("STATIC_DIRECTORY"))
