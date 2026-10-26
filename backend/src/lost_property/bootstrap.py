"""Explicit container setup, followed by a single API worker."""

import os

import uvicorn

from lost_property.config import Settings
from lost_property.main import utcnow
from lost_property.persistence.database import Database
from lost_property.persistence.fixtures import demo_items


def main() -> None:
    settings = Settings()
    database = Database(settings.database_url)
    try:
        database.migrate()
        if os.getenv("DEMO_MODE", "false").lower() == "true":
            from zoneinfo import ZoneInfo

            database.seed(demo_items(utcnow().astimezone(ZoneInfo("Asia/Karachi")).date()))
        database.cleanup(utcnow().timestamp(), settings.idle_seconds)
    finally:
        database.engine.dispose()
    uvicorn.run("lost_property.main:create_app", factory=True, host="0.0.0.0", port=8000, workers=1)


if __name__ == "__main__":
    main()
