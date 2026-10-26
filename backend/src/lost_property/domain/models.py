from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

type Category = Literal["bag", "phone", "wallet", "keys"]
type Stage = Literal[
    "collecting", "disambiguating", "identifying", "confirming", "completed", "cancelled"
]
type OutcomeKind = Literal["lost_report", "claim"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Fields(Model):
    category: Category | None = None
    colour: str | None = None
    brand: str | None = None
    location: str | None = None
    lost_date: str | None = None
    description: str = ""
    uncertain: list[str] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)


class Extraction(Model):
    values: dict[str, str] = Field(default_factory=dict)
    uncertain: list[str] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)
    problem: str | None = None


class FoundItem(Model):
    id: str
    category: Category
    description: str
    colour: str | None = None
    brand: str | None = None
    location: str | None = None
    found_date: date
    private_facts: list[list[str]] = Field(default_factory=list)
    status: Literal["available", "returned"] = "available"


class Candidate(Model):
    item_id: str
    score: float
    signals: dict[str, float]


class Receipt(Model):
    reference: str
    kind: OutcomeKind
    status: Literal["open", "pending_review"]


class Message(Model):
    role: Literal["caller", "assistant"]
    text: str


class Conversation(Model):
    version: int = 0
    search_number: int = 0
    state: Stage = "collecting"
    fields: Fields = Field(default_factory=Fields)
    attempts: dict[str, int] = Field(default_factory=dict)
    asked: str | None = None
    shortlisted: list[str] = Field(default_factory=list)
    selection: str | None = None
    identifying_attempts: int = 0
    details: str = ""
    proposal: OutcomeKind | None = None
    receipt: Receipt | None = None
    restart_pending: bool = False
    transcript: list[Message] = Field(default_factory=list)


class Effect(Model):
    kind: OutcomeKind
    item_id: str | None = None


class Trace(Model):
    rule: str
    explanation: str


class TurnResult(Model):
    conversation: Conversation
    reply: str
    candidates: list[Candidate] = Field(default_factory=list)
    trace: Trace
    effect: Effect | None = None
