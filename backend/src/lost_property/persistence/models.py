from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ItemRow(Base):
    __tablename__ = "found_items"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class SessionRow(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[str] = mapped_column(Text)
    version: Mapped[int]
    turns: Mapped[int]
    created_at: Mapped[float]
    last_seen: Mapped[float]
    expires_at: Mapped[float] = mapped_column(index=True)


class TurnRow(Base):
    __tablename__ = "turns"
    session_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[str] = mapped_column(Text)


class CaseRow(Base):
    __tablename__ = "cases"
    __table_args__ = (UniqueConstraint("session_id", "search_number"),)
    reference: Mapped[str] = mapped_column(String(40), primary_key=True)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    search_number: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))
    item_id: Mapped[str | None] = mapped_column(ForeignKey("found_items.id"))
    payload: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[float] = mapped_column(index=True)
