"""An isolated synthetic-data server owned by the browser test harness."""

from datetime import datetime
from itertools import cycle
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import uvicorn

from lost_property.config import Settings
from lost_property.main import create_app
from lost_property.persistence.database import Database
from lost_property.persistence.fixtures import demo_items

root = Path(__file__).resolve().parents[2]
directory = root / ".artifacts"
directory.mkdir(exist_ok=True)
url = f"sqlite:///{(directory / ('browser-' + uuid4().hex + '.db')).as_posix()}"
db = Database(url)
db.migrate()
db.seed(demo_items(datetime.now(ZoneInfo("Asia/Karachi")).date()))
db.engine.dispose()
# Synthetic browser contexts share one loopback address. Dedicated API tests exercise
# the production limits; this isolated harness gives the test batch its own budget.
settings = Settings(
    database_url=url,
    allowed_origins=("http://127.0.0.1:5181",),
    session_limit=1000,
    turn_limit=1000,
    groq_api_key="synthetic-browser-test",
)
# Browser tests exercise real encoding/upload/API processing without charging a real key.
phrases = cycle(
    ["black backpack with two compartments food court yesterday", "yellow duck keychain", "yes"]
)
transport = httpx.MockTransport(
    lambda _: httpx.Response(200, json={"text": next(phrases), "segments": []})
)
uvicorn.run(
    create_app(settings, speech_transport=transport), host="127.0.0.1", port=8011, access_log=False
)
