from pydantic import BaseModel, Field


class TurnRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class SessionView(BaseModel):
    session_id: str
    state: str
    slots: dict[str, str | None]
    done: bool


class TurnResponse(SessionView):
    reply: str
    intents: list[str]
    actions: list[str]
    trace: list[str]


class StartResponse(SessionView):
    reply: str
