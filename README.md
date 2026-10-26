# Clinic voice assistant

Phone-style assistant that books, reschedules and cancels clinic appointments. The decision logic
is hand-written Python (rules + state machine). No LLM makes any decision.

## Run
```bash
# backend (Python 3.10+)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000
python -m pytest -q                    # tests

# frontend (Node 18+)
cd frontend && npm install && npm run dev   # http://localhost:5173
```
Use Chrome or Edge for the microphone (Web Speech API). A text box is available as a fallback.
Copy `.env.example` to `.env` if you need to change origins or the API URL. No keys are required.

## API
`POST /sessions` starts a call. `POST /sessions/{id}/turn` with `{"text": "..."}` returns the reply,
state, intent, slots and a decision trace.

See `DESIGN.md` for the brain and `AI_USAGE.md` for AI tool usage.
