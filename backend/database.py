import os
from collections.abc import Generator
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class CallerSession(Base):
    __tablename__ = "caller_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision: Mapped[int] = mapped_column(default=0)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Bay(Base):
    __tablename__ = "bays"
    __table_args__ = (UniqueConstraint("session_id", "number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("caller_sessions.id"), index=True)
    number: Mapped[int]


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("caller_sessions.id"), index=True)
    service: Mapped[str] = mapped_column(String(32))
    vehicle: Mapped[str] = mapped_column(String(8))
    start: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="active")
    kind: Mapped[str] = mapped_column(String(16), default="caller")


class Allocation(Base):
    __tablename__ = "allocations"
    __table_args__ = (UniqueConstraint("bay_id", "segment_start"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    bay_id: Mapped[str] = mapped_column(ForeignKey("bays.id"))
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"), index=True)
    segment_start: Mapped[datetime] = mapped_column(DateTime)


class ProcessedTurn(Base):
    __tablename__ = "processed_turns"
    __table_args__ = (UniqueConstraint("session_id", "turn_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("caller_sessions.id"), index=True)
    turn_id: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int]
    text: Mapped[str] = mapped_column(String(1000))
    response: Mapped[dict[str, Any]] = mapped_column(JSON)


def make_engine(url: str | None = None) -> Engine:
    url = url or os.getenv("DATABASE_URL") or "sqlite:///./workshop.db"
    assert url is not None
    if url.startswith(("postgres://", "postgresql://")):
        url = url.replace(url.split(":", 1)[0] + "://", "postgresql+psycopg://", 1)
    sqlite = url.startswith("sqlite")
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 5}
        if sqlite
        else {"connect_timeout": 10},
        pool_pre_ping=True,
    )
    if sqlite:

        @event.listens_for(engine, "connect")
        def sqlite_config(connection: Any, _: Any) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


def sessions(engine: Engine) -> Generator[Session, None, None]:
    with sessionmaker(engine, expire_on_commit=False)() as db:
        yield db
