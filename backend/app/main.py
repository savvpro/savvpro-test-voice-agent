from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .brain import Session, handle

app = FastAPI(title="SAVV Voice Agent")

# Allow the frontend to call us (relax in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatIn(BaseModel):
    session_id: str
    text: str


class ChatOut(BaseModel):
    reply: str
    state: str
    slots: dict
    debug: dict


SESSIONS: dict[str, Session] = {}


@app.post("/chat", response_model=ChatOut)
def chat(req: ChatIn):
    session = SESSIONS.setdefault(req.session_id, Session())
    reply, session, debug = handle(session, req.text)
    SESSIONS[req.session_id] = session
    return ChatOut(
        reply=reply,
        state=session.state.value,
        slots={
            "day": session.day,
            "time": session.time,
            "party_size": session.party_size,
            "name": session.name,
            "booking_id": session.booking_id,
        },
        debug=debug,
    )


@app.post("/reset/{session_id}")
def reset(session_id: str):
    SESSIONS.pop(session_id, None)
    return {"ok": True}