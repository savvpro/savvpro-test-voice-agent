from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, create_engine, delete, event, inspect
from sqlalchemy.orm import sessionmaker

from lost_property.domain.models import FoundItem
from lost_property.persistence.models import CaseRow, ItemRow, SessionRow


class Database:
    def __init__(self, url: str) -> None:
        if not url.startswith("sqlite:///") or url.endswith(":memory:"):
            raise ValueError("Use a file-backed SQLite URL for the single-instance deployment.")
        self.url = url
        self.engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 10})

        # SQLAlchemy owns BEGIN. IMMEDIATE serializes short transactions before reading,
        # avoiding SQLite's read-to-write upgrade race during concurrent confirmations.
        def connect(dbapi: object, _: object) -> None:
            from sqlite3 import Connection as SQLiteConnection

            if isinstance(dbapi, SQLiteConnection):
                dbapi.isolation_level = None
                dbapi.execute("PRAGMA foreign_keys=ON")
                dbapi.execute("PRAGMA busy_timeout=10000")

        def begin(connection: Connection) -> None:
            connection.exec_driver_sql("BEGIN IMMEDIATE")

        event.listen(self.engine, "connect", connect)
        event.listen(self.engine, "begin", begin)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def migrate(self) -> None:
        migrations = Path(__file__).resolve().parents[1] / "migrations"
        config = Config()
        config.set_main_option("script_location", str(migrations))
        config.set_main_option("sqlalchemy.url", self.url.replace("%", "%%"))
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    def ready(self) -> bool:
        return {"found_items", "conversations", "turns", "cases", "alembic_version"}.issubset(
            inspect(self.engine).get_table_names()
        )

    def seed(self, items: list[FoundItem]) -> int:
        inserted = 0
        with self.sessions.begin() as session:
            for item in items:
                if session.get(ItemRow, item.id) is None:
                    session.add(ItemRow(id=item.id, payload=item.model_dump_json()))
                    inserted += 1
        return inserted

    def cleanup(self, now: float, idle_seconds: int = 1800) -> tuple[int, int]:
        with self.sessions.begin() as session:
            cases = list(
                session.scalars(
                    delete(CaseRow).where(CaseRow.expires_at <= now).returning(CaseRow.reference)
                )
            )
            chats = list(
                session.scalars(
                    delete(SessionRow)
                    .where(
                        (SessionRow.expires_at <= now)
                        | (SessionRow.last_seen <= now - idle_seconds)
                    )
                    .returning(SessionRow.id)
                )
            )
        return len(chats), len(cases)
