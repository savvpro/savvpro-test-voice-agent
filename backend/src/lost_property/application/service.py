import hashlib
import secrets
from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from lost_property.api.schemas import CandidateView, SessionView, TurnRequest
from lost_property.config import Settings
from lost_property.domain.dialogue import GREETING, respond
from lost_property.domain.matching import rank
from lost_property.domain.models import Candidate, Conversation, FoundItem, Message, Receipt, Trace
from lost_property.persistence.database import Database
from lost_property.persistence.models import CaseRow, ItemRow, SessionRow, TurnRow


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def public_view(
    state: Conversation,
    inventory: list[FoundItem],
    trace: Trace | None = None,
    ranked: list[Candidate] | None = None,
) -> SessionView:
    by_id = {item.id: item for item in inventory}
    candidates: list[CandidateView] = []
    for candidate in ranked if ranked is not None else rank(state.fields, inventory):
        if candidate.score < 40 or len(candidates) == 3:
            continue
        item = by_id[candidate.item_id]
        candidates.append(
            CandidateView(
                label=f"Option {len(candidates) + 1}",
                category=item.category,
                description=item.description,
                colour=item.colour,
                score=candidate.score,
                signals=candidate.signals,
            )
        )
    return SessionView(
        version=state.version,
        state=state.state,
        reply=state.transcript[-1].text if state.transcript else GREETING,
        fields=state.fields,
        candidates=candidates,
        trace=trace
        or Trace(
            rule="ready",
            explanation="The Python rules choose each next step from the supplied information.",
        ),
        transcript=state.transcript,
        proposal=state.proposal,
        receipt=state.receipt,
        restart_pending=state.restart_pending,
    )


class ConversationService:
    def __init__(self, db: Database, settings: Settings, clock: Callable[[], datetime]) -> None:
        self.db, self.settings, self.clock = db, settings, clock

    def _inventory(self, session: Session) -> list[FoundItem]:
        return [
            FoundItem.model_validate_json(row.payload) for row in session.scalars(select(ItemRow))
        ]

    def _session(self, db: Session, token: str | None) -> SessionRow:
        if token is None or len(token) > 128:
            raise AppError(401, "SESSION_EXPIRED", "Start a new conversation to continue.")
        row = db.scalar(select(SessionRow).where(SessionRow.token_hash == token_hash(token)))
        now = self.clock().timestamp()
        if (
            row is None
            or row.expires_at <= now
            or row.last_seen <= now - self.settings.idle_seconds
        ):
            raise AppError(401, "SESSION_EXPIRED", "Start a new conversation to continue.")
        return row

    def open(self, token: str | None) -> tuple[SessionView, str | None]:
        with self.db.sessions.begin() as session:
            if token:
                try:
                    row = self._session(session, token)
                except AppError:
                    row = None
                if row is not None:
                    row.last_seen = self.clock().timestamp()
                    return public_view(
                        Conversation.model_validate_json(row.payload), self._inventory(session)
                    ), None
            now = self.clock().timestamp()
            capability = secrets.token_urlsafe(32)
            state = Conversation(transcript=[Message(role="assistant", text=GREETING)])
            session.add(
                SessionRow(
                    id=str(uuid4()),
                    token_hash=token_hash(capability),
                    payload=state.model_dump_json(),
                    version=0,
                    turns=0,
                    created_at=now,
                    last_seen=now,
                    expires_at=now + self.settings.absolute_seconds,
                )
            )
            return public_view(state, []), capability

    def get(self, token: str | None) -> SessionView:
        with self.db.sessions.begin() as session:
            row = self._session(session, token)
            row.last_seen = self.clock().timestamp()
            return public_view(
                Conversation.model_validate_json(row.payload), self._inventory(session)
            )

    def erase(self, token: str | None) -> None:
        with self.db.sessions.begin() as session:
            row = self._session(session, token)
            session.delete(row)

    def turn(self, token: str | None, request: TurnRequest) -> SessionView:
        fingerprint = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        now = self.clock()
        with self.db.sessions.begin() as session:
            row = self._session(session, token)
            previous = session.get(TurnRow, (row.id, str(request.request_id)))
            if previous:
                if previous.request_hash != fingerprint:
                    raise AppError(
                        409, "REQUEST_CONFLICT", "This request identifier was already used."
                    )
                return SessionView.model_validate_json(previous.response)
            if request.expected_version != row.version:
                raise AppError(
                    409, "VERSION_CONFLICT", "The conversation changed. Refresh and try again."
                )
            if row.turns >= 60:
                raise AppError(
                    429, "TURN_LIMIT", "This conversation reached its limit. Start a new one."
                )
            state = Conversation.model_validate_json(row.payload)
            inventory = self._inventory(session)
            result = respond(state, request.text, inventory, now)
            state = result.conversation
            if result.effect:
                receipt = Receipt(
                    reference="LF-" + secrets.token_hex(6).upper(),
                    kind=result.effect.kind,
                    status="pending_review" if result.effect.kind == "claim" else "open",
                )
                session.add(
                    CaseRow(
                        reference=receipt.reference,
                        session_id=row.id,
                        search_number=state.search_number,
                        kind=receipt.kind,
                        item_id=result.effect.item_id,
                        payload=state.fields.model_dump_json(),
                        expires_at=now.timestamp() + 30 * 86400,
                    )
                )
                state.state = "completed"
                state.receipt = receipt
                state.proposal = None
                state.transcript[-1].text = (
                    f"Your reference is {receipt.reference}. "
                    + (
                        "Your possible-match claim is pending staff review. "
                        if receipt.kind == "claim"
                        else "Your lost-item report has been recorded. "
                    )
                    + "Visit the information desk for staff assistance; "
                    "ownership must be checked before release."
                )
            view = public_view(state, inventory, result.trace, result.candidates)
            # Keep the comparison in SQL as well as checking the loaded version.
            changed = session.scalar(
                update(SessionRow)
                .where(SessionRow.id == row.id, SessionRow.version == request.expected_version)
                .values(
                    payload=state.model_dump_json(),
                    version=state.version,
                    turns=row.turns + 1,
                    last_seen=now.timestamp(),
                )
                .returning(SessionRow.id)
            )
            if changed is None:
                raise AppError(
                    409, "VERSION_CONFLICT", "The conversation changed. Refresh and try again."
                )
            session.add(
                TurnRow(
                    session_id=row.id,
                    request_id=str(request.request_id),
                    request_hash=fingerprint,
                    response=view.model_dump_json(),
                )
            )
        # Return only after the transaction context committed successfully.
        return view
