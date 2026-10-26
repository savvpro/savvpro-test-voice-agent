from datetime import UTC, datetime

from sqlalchemy import select

from lost_property.api.schemas import TurnRequest
from lost_property.application.service import ConversationService
from lost_property.config import Settings
from lost_property.persistence.database import Database
from lost_property.persistence.models import CaseRow, SessionRow, TurnRow


def test_retention_removes_ledgers_but_preserves_cases_until_their_boundary(tmp_path):
    from uuid import uuid4

    now = datetime(2026, 10, 26, 12, tzinfo=UTC)
    db = Database(f"sqlite:///{(tmp_path / 'retention.db').as_posix()}")
    db.migrate()
    service = ConversationService(db, Settings(database_url=db.url), lambda: now)
    _, token = service.open(None)
    proposal = service.turn(
        token,
        TurnRequest(
            request_id=uuid4(), expected_version=0, text="purple wallet with stars yesterday"
        ),
    )
    completed = service.turn(
        token, TurnRequest(request_id=uuid4(), expected_version=proposal.version, text="yes")
    )
    assert completed.receipt is not None
    assert db.cleanup(now.timestamp() + 86400) == (1, 0)
    with db.sessions() as session:
        assert list(session.scalars(select(SessionRow))) == []
        assert list(session.scalars(select(TurnRow))) == []
        case = session.scalar(select(CaseRow))
        assert case is not None and case.session_id is None
    assert db.cleanup(now.timestamp() + 30 * 86400) == (0, 1)
    db.engine.dispose()
