import json
import platform
import statistics
import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from lost_property.api.schemas import TurnRequest
from lost_property.application.service import ConversationService
from lost_property.config import Settings
from lost_property.persistence.database import Database
from lost_property.persistence.fixtures import demo_items


@pytest.mark.performance
def test_text_turn_p95_with_one_thousand_items(tmp_path):
    now = datetime.now(UTC)
    database = Database(f"sqlite:///{(tmp_path / 'latency.db').as_posix()}")
    database.migrate()
    originals = demo_items(now.date())
    inventory = [
        originals[index % 24].model_copy(update={"id": f"performance-{index}"})
        for index in range(1000)
    ]
    database.seed(inventory)
    service = ConversationService(database, Settings(database_url=database.url), lambda: now)
    durations = []
    for _batch in range(5):
        _, token = service.open(None)
        version = 0
        for index in range(42):
            started = time.perf_counter()
            reply = service.turn(
                token,
                TurnRequest(
                    request_id=uuid4(),
                    expected_version=version,
                    text="black backpack" if index == 0 else "repeat",
                ),
            )
            elapsed = (time.perf_counter() - started) * 1000
            version = reply.version
            if index >= 2:
                durations.append(elapsed)
    p95 = statistics.quantiles(durations, n=100)[94]
    result = {
        "turns": len(durations),
        "inventory_items": 1000,
        "p95_ms": round(p95, 2),
        "median_ms": round(statistics.median(durations), 2),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "os": platform.system(),
    }
    print(json.dumps(result))
    assert len(durations) == 200
    assert p95 <= 300, f"Text-turn p95 exceeded the documented local release budget: {p95:.2f} ms"
    database.engine.dispose()
