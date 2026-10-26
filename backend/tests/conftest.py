import sqlite3
from collections.abc import Iterator
from datetime import datetime

import pytest

NOW = datetime(2026, 10, 26, 10, 0)
TODAY = NOW.date()


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    from app import db

    c = db.connect(":memory:")
    db.init_db(c)
    db.seed(c, TODAY)
    yield c
    c.close()
