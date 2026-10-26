"""Shared route dependencies."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.services.conversation import ConversationService


def get_conversation(request: Request) -> ConversationService:
    return request.app.state.conversation


def get_db(request: Request) -> Iterator[Session]:
    # Same database the conversation writes to (an in-memory one in tests).
    with get_conversation(request).session_factory() as session:
        yield session
