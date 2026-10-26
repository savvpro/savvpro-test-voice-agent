"""ORM models.

All datetimes are naive and expressed in the clinic's local timezone
(settings.clinic_timezone). SQLite has no timezone-aware column type, and the
clinic only ever operates in one timezone.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AppointmentStatus(StrEnum):
    BOOKED = "booked"
    CANCELLED = "cancelled"


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")

    doctors: Mapped[list[Doctor]] = relationship(back_populates="department")


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)

    department: Mapped[Department] = relationship(back_populates="doctors")
    slots: Mapped[list[Slot]] = relationship(back_populates="doctor")


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (UniqueConstraint("doctor_id", "start_time", name="uq_slot_doctor_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False)

    doctor: Mapped[Doctor] = relationship(back_populates="slots")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32), unique=True)

    appointments: Mapped[list[Appointment]] = relationship(back_populates="patient")


class Appointment(Base):
    __tablename__ = "appointments"
    # A slot can hold only one *active* booking. Cancelled appointments keep
    # their slot_id for history, so the uniqueness is a partial index; a plain
    # unique column would make a cancelled slot impossible to book again.
    __table_args__ = (
        Index(
            "uq_appointment_active_slot",
            "slot_id",
            unique=True,
            sqlite_where=text("status = 'booked'"),
            postgresql_where=text("status = 'booked'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_ref: Mapped[str] = mapped_column(String(16), unique=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), index=True)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(
            AppointmentStatus,
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=AppointmentStatus.BOOKED,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    patient: Mapped[Patient] = relationship(back_populates="appointments")
    slot: Mapped[Slot] = relationship()
