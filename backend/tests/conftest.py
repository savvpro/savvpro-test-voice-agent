from datetime import date, datetime

import pytest
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_database
from app.db.session import create_db_engine

# A fixed Monday in the future so slot dates never depend on the real clock.
REF_MONDAY = date(2030, 1, 7)
NOW = datetime(2030, 1, 7, 8, 0)


@pytest.fixture
def engine():
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def seeded(session):
    """One week of slots starting REF_MONDAY, nothing pre-booked."""
    seed_database(session, start=REF_MONDAY, days=7, prebook_ratio=0.0)
    return session


@pytest.fixture(scope="session")
def classifier(tmp_path_factory):
    """Intent classifier trained from intents.yaml into a temp dir (not the committed model)."""
    from app.nlu.classifier import IntentClassifier
    from app.nlu.train import fit_and_save

    path = tmp_path_factory.mktemp("nlu") / "nlu.joblib"
    fit_and_save(path)
    return IntentClassifier(path)


# Monday 7 January 2030, before opening: every slot of the month is in the future.
CALL_NOW = datetime(2030, 1, 7, 8, 0)


@pytest.fixture
def clinic(session):
    """A month of free slots from REF_MONDAY (nothing pre-booked)."""
    seed_database(session, start=REF_MONDAY, days=31, prebook_ratio=0.0)
    return session


@pytest.fixture
def call(clinic, classifier):
    """Start a phone call: ``c = call(); c.say("...")``."""
    from tests.conversation import Call

    def start(now: datetime = CALL_NOW) -> Call:
        return Call(clinic, classifier, now)

    return start


@pytest.fixture
def make_conversation(engine, classifier):
    """A ConversationService over a month of free slots, with fake speech by default."""
    from sqlalchemy.orm import sessionmaker

    from app.services.conversation import ConversationService
    from app.services.session_store import SessionStore
    from tests.fakes import FakeSTT, FakeTTS

    with Session(engine) as db:
        seed_database(db, start=REF_MONDAY, days=31, prebook_ratio=0.0)

    fake = object()

    def build(stt=fake, tts=fake) -> ConversationService:
        return ConversationService(
            session_factory=sessionmaker(bind=engine, expire_on_commit=False),
            store=SessionStore(),
            classifier=classifier,
            stt=FakeSTT() if stt is fake else stt,
            tts=FakeTTS() if tts is fake else tts,
            now=lambda: CALL_NOW,
            seed=0,
        )

    return build


@pytest.fixture
def client(make_conversation):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(make_conversation())) as client:
        yield client


def pytest_collection_modifyitems(config, items):
    """Tests marked ``slow`` load real speech models: run them with RUN_SLOW=1."""
    import os

    if os.environ.get("RUN_SLOW") == "1":
        return
    skip = pytest.mark.skip(reason="slow: set RUN_SLOW=1 (make test-slow)")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
