import os
import uuid
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .brain import Brain, Session
from .schedule import Schedule

app = FastAPI(title="Voice Agent Brain")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(","),
                   allow_methods=["*"], allow_headers=["*"])
brain = Brain(Schedule(date.today()))
sessions: dict[str, Session] = {}


class TurnIn(BaseModel):
    text: str = ""


def _out(sid, t):
    return {"session_id": sid, "reply": t.reply, "state": t.state, "intent": t.intent,
            "slots": t.slots, "trace": t.trace, "done": t.done}


@app.post("/sessions")
def start():
    sid, s = uuid.uuid4().hex, Session()
    sessions[sid] = s
    return _out(sid, brain.greet(s))


@app.post("/sessions/{sid}/turn")
def turn(sid: str, body: TurnIn):
    s = sessions.get(sid)
    if not s:
        raise HTTPException(404, "unknown session")
    return _out(sid, brain.handle(s, body.text))


@app.get("/health")
def health():
    return {"ok": True}
