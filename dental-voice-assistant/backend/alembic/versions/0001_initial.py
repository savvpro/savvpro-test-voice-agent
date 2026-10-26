"""Initial migration — create appointments table.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-26 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("patient_name", sa.Text(), nullable=False),
        sa.Column("patient_phone", sa.String(length=20), nullable=False),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'confirmed'"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_appointments_patient_phone"),
        "appointments",
        ["patient_phone"],
        unique=False,
    )
    # Partial unique index: only one confirmed booking per slot
    op.create_index(
        "uq_confirmed_slot",
        "appointments",
        ["appointment_date", "start_time"],
        unique=True,
        postgresql_where=sa.text("status = 'confirmed'"),
        sqlite_where=sa.text("status = 'confirmed'"),
    )


def downgrade() -> None:
    op.drop_index("uq_confirmed_slot", table_name="appointments")
    op.drop_index(op.f("ix_appointments_patient_phone"), table_name="appointments")
    op.drop_table("appointments")
