# Children's Specialist Clinic appointment assistant

A deterministic voice and text assistant for booking, checking, cancelling, and rescheduling children's specialist appointments.

```text
Caller → browser speech-to-text → FastAPI → nlu.py + dialogue.py → SQLite
Caller ← browser text-to-speech ← deterministic Python reply
```

No LLM is used. The browser only converts speech to text and text to speech; the Python backend owns intent extraction, validation, token selection, confirmation, and persistence.

## Clinic schedule

- Weekdays only (Monday–Friday); weekends and past dates are rejected.
- 35 generated daily tokens, starting at 9:00 AM.
- Each consecutive slot is 14 minutes; the last starts at 4:56 PM and ends at 5:10 PM.
- Token times are generated from the configured opening time, duration, and capacity.
- Cancelled tokens are available for reuse; appointment and audit records remain preserved.

## Run it

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
uvicorn app.main:app --reload --port 8000

# Frontend, in another terminal
cd frontend
npm install
npm run dev
```

Use Chrome or Edge for microphone input. Typed conversation works in other browsers.

## Backend API

- `POST /api/call` — start a conversation.
- `POST /api/turn` — submit a caller utterance.
- `GET /api/schedule?date=YYYY-MM-DD` — generated daily slots and active occupancy.
- `GET /api/appointments/{id}/history` — audit history for one appointment.
- `GET /api/health` — health check.

The SQLite database stores appointment history, active token assignments, stateful calls, conversation turns, and audit events. Partial unique constraints and `BEGIN IMMEDIATE` transactions protect token allocation across concurrent connections.
