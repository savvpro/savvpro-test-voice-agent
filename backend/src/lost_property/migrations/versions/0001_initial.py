"""Initial inventory, conversation, retry ledger, and case schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "found_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("turns", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("last_seen", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_conversations_expires_at", "conversations", ["expires_at"])
    op.create_table(
        "turns",
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
    )
    op.create_table(
        "cases",
        sa.Column("reference", sa.String(40), primary_key=True),
        sa.Column(
            "session_id", sa.String(64), sa.ForeignKey("conversations.id", ondelete="SET NULL")
        ),
        sa.Column("search_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("item_id", sa.String(64), sa.ForeignKey("found_items.id")),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("session_id", "search_number"),
    )
    op.create_index("ix_cases_expires_at", "cases", ["expires_at"])


def downgrade() -> None:
    op.drop_table("cases")
    op.drop_table("turns")
    op.drop_table("conversations")
    op.drop_table("found_items")
