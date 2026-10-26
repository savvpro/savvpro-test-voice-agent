from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from brain.brain import handle_turn
from brain.state import Session

app = FastAPI(title="Appointment Assistant API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, Session] = {}


class TurnRequest(BaseModel):
    session_id: str
    text: str


class ResetRequest(BaseModel):
    session_id: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/turn")
def turn(request: TurnRequest) -> dict:
    session = sessions.get(request.session_id, Session())
    updated, reply, decision = handle_turn(session, request.text)
    sessions[request.session_id] = updated
    return {
        "reply": reply,
        "decision": decision,
        "session_id": request.session_id,
    }


@app.post("/reset")
def reset(request: ResetRequest) -> dict[str, bool]:
    sessions.pop(request.session_id, None)
    return {"ok": True}
