"""All mutating turns acquire SQLite's writer lock before reading state.

The booking write, session update and idempotency receipt commit together.
This also serializes independent workers, unlike an in-process mutex.
"""
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import ForeignKey, Integer, JSON, String, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class Appointment(Base):
    __tablename__ = "appointments"
    reference: Mapped[str] = mapped_column(String(16), primary_key=True)
    service: Mapped[str] = mapped_column(String(20))
    customer_name: Mapped[str] = mapped_column(String(80))
    starts_at: Mapped[int] = mapped_column(Integer, index=True)
    ends_at: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="confirmed", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Receipt(Base):
    __tablename__ = "turn_receipts"
    __table_args__ = (UniqueConstraint("session_id", "request_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    request_id: Mapped[str] = mapped_column(String(100))
    request_text: Mapped[str] = mapped_column(String(1000))
    expected_revision: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict] = mapped_column(JSON)


class Database:
    def __init__(self, url: str):
        if not url.startswith("sqlite:"):
            raise ValueError("This application supports SQLite only.")
        options = {"poolclass": StaticPool} if ":memory:" in url else {}
        self.engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 10}, **options)

        @event.listens_for(self.engine, "connect")
        def configure(dbapi_connection, _):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
            dbapi_connection.execute("PRAGMA busy_timeout=10000")

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        with Session(self.engine, expire_on_commit=False) as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
