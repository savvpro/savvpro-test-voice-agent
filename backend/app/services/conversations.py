"""Coordinate the existing FSM and SQLite without adding decisions to routes."""

from copy import deepcopy
from dataclasses import dataclass, field, fields
from datetime import datetime
import sqlite3
from threading import Lock
import uuid

from app.brain.engine import ConversationEngine, ConversationSession, EngineResponse
from app.brain.parser import IntentParser
from app.brain.responses import slot_unavailable, details_expired
from app.brain.states import ConversationState, Intent
from app.database import InvalidReservationError, Reservation, ReservationStore, UnavailableError


class UnknownSessionError(Exception):
    """No live conversation exists for the supplied opaque session ID."""


class MessageConflictError(Exception):
    """A message ID was reused with different text."""


class StorageUnavailableError(Exception):
    """The caller can safely retry the original request after a storage error."""


@dataclass(frozen=True)
class ConversationReply:
    message: str
    session_id: str
    status: str
    collected_data: dict
    reservation: Reservation | None = None


@dataclass
class _SessionContext:
    lock: Lock = field(default_factory=Lock)
    booking_key: str = field(default_factory=lambda: uuid.uuid4().hex)
    reservation: Reservation | None = None
    messages: dict[str, tuple[str, ConversationReply]] = field(default_factory=dict)


class ConversationService:
    """One-process session state, serialized per session, with durable bookings.

    Message IDs deduplicate complete turns. A separate server-owned booking key
    deduplicates writes even when clients retry confirmation with a new message ID.
    """

    def __init__(self, store: ReservationStore, *, reference_date: datetime | None = None):
        self.store = store
        self.engine = ConversationEngine(reference_date=reference_date)
        self._parser = IntentParser()
        self._reference_date = reference_date
        self._contexts: dict[str, _SessionContext] = {}
        self._contexts_lock = Lock()

    def start_conversation(self) -> ConversationReply:
        with self._contexts_lock:
            sid = self.engine.create_session()
            self._contexts[sid] = _SessionContext()
            return self._reply(self.engine.start_conversation(sid), None)

    def process_message(self, session_id: str, message: str, request_id: str) -> ConversationReply:
        with self._contexts_lock:
            context = self._contexts.get(session_id)
        if context is None:
            raise UnknownSessionError()

        with context.lock:
            cached = context.messages.get(request_id)
            if cached is not None:
                if cached[0] != message:
                    raise MessageConflictError()
                return deepcopy(cached[1])

            session = self.engine.get_session(session_id)
            before = deepcopy(session)
            prior_reservation, prior_key = context.reservation, context.booking_key
            try:
                # Reuse the existing parser solely to identify global restart
                # and whether information was supplied; the FSM decides the turn.
                intent = self._parser.parse(message, self._reference_date).intent
                response = self.engine.process_input(session_id, message)
                if intent == Intent.RESTART:
                    context.booking_key = uuid.uuid4().hex
                    context.reservation = None

                if (
                    response.state == ConversationState.COMPLETED.value
                    and before.state != ConversationState.COMPLETED
                ):
                    # The brain has accepted an explicit confirmation. Never
                    # return its success message until the transaction succeeds.
                    try:
                        context.reservation = self.store.create_reservation(
                            session.date, session.time, session.party_size,
                            request_id=context.booking_key,
                        )
                    except UnavailableError:
                        response = self._unavailable(session)
                    except InvalidReservationError:
                        response = self._expired(session)
                elif (
                    response.state == ConversationState.CONFIRM.value
                    and (
                        before.state != ConversationState.CONFIRM
                        or intent in {
                            Intent.PROVIDE_INFO, Intent.CHANGE_DATE,
                            Intent.CHANGE_TIME, Intent.CHANGE_PARTY_SIZE,
                        }
                    )
                ):
                    # A read before presenting the details is advisory. The
                    # create transaction checks again if the customer says yes.
                    try:
                        available = self.store.check_availability(
                            session.date, session.time, session.party_size,
                        )
                        if not available:
                            response = self._unavailable(session)
                    except InvalidReservationError:
                        response = self._expired(session)

                reply = self._reply(response, context.reservation)
            except Exception as error:
                # A failed turn must not strand the FSM in COMPLETED. Keep the
                # booking key for safe recovery of an uncertain commit result.
                for attribute in fields(ConversationSession):
                    setattr(session, attribute.name, getattr(before, attribute.name))
                context.reservation, context.booking_key = prior_reservation, prior_key
                if isinstance(error, (sqlite3.Error, OSError)):
                    raise StorageUnavailableError() from error
                raise

            context.messages[request_id] = (message, deepcopy(reply))
            return reply

    @staticmethod
    def _unavailable(session: ConversationSession) -> EngineResponse:
        session.time = None
        session.state = ConversationState.ASK_TIME
        return ConversationService._follow_up(session, slot_unavailable())

    @staticmethod
    def _expired(session: ConversationSession) -> EngineResponse:
        session.date = None
        session.state = ConversationState.ASK_DATE
        return ConversationService._follow_up(session, details_expired())

    @staticmethod
    def _follow_up(session: ConversationSession, message: str) -> EngineResponse:
        session.history[-1]["assistant"] = message
        return EngineResponse(message, session.state.value, session.collected_data(), session.session_id)

    @staticmethod
    def _reply(response: EngineResponse, reservation: Reservation | None) -> ConversationReply:
        return ConversationReply(
            message=response.message, session_id=response.session_id,
            status=response.state, collected_data=response.collected_data,
            reservation=reservation,
        )
