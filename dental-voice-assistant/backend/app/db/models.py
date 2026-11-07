"""SQLAlchemy ORM models.

Schema
------
appointments
  id               UUID PK
  patient_name     TEXT  NOT NULL
  patient_phone    TEXT  NOT NULL  (stored normalised, no dashes/spaces)
  service          TEXT  NOT NULL
  appointment_date DATE  NOT NULL
  start_time       TIME  NOT NULL
  end_time         TIME  NOT NULL
  status           TEXT  NOT NULL  default 'confirmed'
  created_at       TIMESTAMP WITH TIME ZONE  default now()
  cancelled_at     TIMESTAMP WITH TIME ZONE  nullable

Partial unique index: one confirmed booking per (date, start_time).
  Postgres: WHERE status = 'confirmed'
  SQLite:   WHERE status = 'confirmed'
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    Index,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Appointment(Base):
    """A dental appointment booking."""

    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_name: Mapped[str] = mapped_column(Text, nullable=False)
    patient_phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    service: Mapped[str] = mapped_column(String(100), nullable=False)
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'confirmed'"), default="confirmed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    __table_args__ = (
        # Partial unique index: only one confirmed booking per slot
        Index(
            "uq_confirmed_slot",
            "appointment_date",
            "start_time",
            unique=True,
            postgresql_where=text("status = 'confirmed'"),
            sqlite_where=text("status = 'confirmed'"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Appointment id={self.id!r} date={self.appointment_date} "
            f"start={self.start_time} status={self.status!r}>"
        )
