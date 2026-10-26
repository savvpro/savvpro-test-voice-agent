"""Settings come from environment variables (see .env.example). No secrets live in code."""
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
            if origin.strip()
        ]
    )
    seed_demo_data: bool = os.getenv("SEED_DEMO_DATA", "true").lower() == "true"
    max_sessions: int = int(os.getenv("MAX_SESSIONS", "500"))
