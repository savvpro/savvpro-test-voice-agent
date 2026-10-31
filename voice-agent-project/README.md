# Green Valley Clinic: Voice Assistant

A phone-style voice assistant that **books, reschedules and cancels clinic appointments**.
The caller talks, the assistant listens, decides and talks back.

```
Caller speaks → Speech to text → The brain (own Python code) → Text to speech → Caller hears the reply
```

* **The brain is plain Python**: a rule-based language-understanding layer plus a finite state machine.
  There is **no GPT / Claude / Gemini / any ML model** making decisions. See [DESIGN.md](DESIGN.md).
* **Frontend** (Next.js): talk with your microphone or type, and watch what the brain decided on every turn
  (state change, rule fired, intents, entities, slots).
* **All data is fake.** The schedule is generated, and the two demo patients are invented.

## Requirements

* Python 3.10+ and Node.js 18+
* Chrome or Edge for voice (they provide the browser speech APIs). Any browser works with the typing box.
* No API keys, accounts or paid services are needed.

## Run it

### 1. Backend (terminal 1)

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# macOS / Linux:       source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

The API now runs on http://localhost:8000 (docs at http://localhost:8000/docs).
Configuration is optional and read from environment variables; see `backend/.env.example`.

### 2. Frontend (terminal 2)

```bash
cd frontend
# Windows: copy .env.local.example .env.local      macOS/Linux: cp .env.local.example .env.local
npm install
npm run dev
```

Open http://localhost:3000, press **Start call**, allow the microphone, and talk.
By default the assistant speaks its replies and starts listening again by itself (hands-free).
Untick the toggles for manual mode, or use the typing box.

## Things to try

| Say | What it shows |
|---|---|
| "Book a dental appointment tomorrow morning" | several slots in one sentence, then time-of-day options |
| "Friday at 4 PM" → (then) "actually make it 11" | change of mind, acknowledged out loud |
| "No, I said 10 AM, not 11 AM" | correction handling |
| a slot that is busy | alternatives offered, pick with "the second one" |
| "Sunday" | closed day explained, asks again |
| "What are your opening hours?" mid-booking | answers, then returns to the open question |
| "Reschedule my appointment" → 0300 1234567 | finds the demo patient (Sara Malik) and moves the appointment |
| "Cancel my appointment" → 0311 1234567 | cancel with read-back and confirmation |
| say nothing, or mumble, three times | re-prompt, rephrase, then hand-off to a human |
| "Let me talk to a person" | hand-off at any time |

Demo patients (invented): **Sara Malik** `03001234567` (general) and **Ali Raza** `03111234567` (dental).
Each has one appointment on the next open day, so reschedule and cancel can be tried right away.

## Tests

```bash
cd backend
pytest -q                         # 119 tests, ~1 second
pytest --cov=app --cov-report=term-missing   # needs: pip install pytest-cov  (96 % line coverage)
ruff check . && ruff format --check .
cd ../frontend
npm run lint && npm run build     # type-check and production build
```

Tests use a fixed clock (Monday, 2 Nov 2026) so they never depend on today's date.
The biggest suite is `tests/test_dialogue_scenarios.py`: scripted phone calls, one per messy-caller case.

## API

| Method & path | Purpose |
|---|---|
| `POST /api/sessions` | start a call; returns the greeting |
| `POST /api/sessions/{id}/turn` | body `{"text": "...", "confidence": 0.9}`; empty text means silence |
| `DELETE /api/sessions/{id}` | end the call |
| `GET /health` | liveness check |

Every turn response includes `reply`, `state`, `slots`, `ended` and a `trace` explaining the decision.

## Project layout

```
backend/
  app/
    brain/        nlu.py · datetime_parse.py · phone.py · policy.py (state machine) · formatting.py · models.py
    services/     scheduler.py (fake schedule) · sessions.py (in-memory store with expiry)
    api/          routes.py · schemas.py
    main.py       app factory, CORS, logging     config.py   env settings
  tests/          unit + scripted-call + API tests
frontend/         Next.js app: voice controls, transcript, decision panel
.github/workflows/ci.yml   lint + tests + build on every push
```

## Limitations

Speech recognition and synthesis use the browser's built-in Web Speech API, so voice needs Chrome or Edge and
an internet connection for recognition. The `/turn` endpoint takes plain text, so a server-side speech engine
could replace the browser without touching the brain. Sessions live in memory (one server process).
