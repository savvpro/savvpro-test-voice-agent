from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import SessionView, StartResponse, TurnRequest, TurnResponse
from app.brain.assistant import Assistant

router = APIRouter(prefix="/api")


def _view(session_id: str, bot: Assistant) -> dict:
    session = bot.session
    return {
        "session_id": session_id,
        "state": session.state.value,
        "slots": session.slots(),
        "done": session.state.value == "done",
    }


def _store(request: Request):
    return request.app.state.store


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/sessions", response_model=StartResponse, status_code=201)
def start_session(request: Request) -> dict:
    session_id, bot = _store(request).create()
    result = bot.start()
    return {**_view(session_id, bot), "reply": result.reply}


@router.get("/sessions/{session_id}", response_model=SessionView)
def get_session(session_id: str, request: Request) -> dict:
    bot = _store(request).get(session_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    return _view(session_id, bot)


@router.post("/sessions/{session_id}/turns", response_model=TurnResponse)
def take_turn(session_id: str, body: TurnRequest, request: Request) -> dict:
    bot = _store(request).get(session_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text is empty")
    result = bot.hear(text)
    return {
        **_view(session_id, bot),
        "reply": result.reply,
        "intents": sorted(result.nlu.intents) if result.nlu else [],
        "actions": result.actions,
        "trace": result.trace,
    }
