"""Browser-test server only: isolated disposable database and fixed clock."""
import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from app.config import Settings
from app.main import create_app

directory = TemporaryDirectory(prefix="voxdesk-e2e-")
settings = Settings(database_url=f"sqlite:///{Path(directory.name) / 'browser.db'}",
                    cors_origins=tuple(os.getenv("VOXDESK_CORS_ORIGINS", ",".join(Settings.cors_origins)).split(",")))
app = create_app(settings, lambda: datetime(2026, 10, 26, 9, tzinfo=ZoneInfo("Asia/Karachi")))
