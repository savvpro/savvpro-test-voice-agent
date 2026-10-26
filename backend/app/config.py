"""Settings read from the environment. Nothing secret is needed to run."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    cors_origins: tuple[str, ...]
    max_calls: int


def load_settings() -> Settings:
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return Settings(
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        max_calls=int(os.getenv("MAX_CALLS", "200")),
    )
