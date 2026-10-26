# Maple Street Clinic Voice Agent

A phone-style voice assistant that **books, reschedules and cancels appointments** at a fictional clinic. The caller talks in the browser; speech is transcribed, a rule-based Python brain (no LLM) decides what to do, and the reply is spoken back. The page shows what the brain decided on every turn.

The assessment brief is in [TASK.md](TASK.md). Design: [DESIGN.md](DESIGN.md). AI tooling: [AI_USAGE.md](AI_USAGE.md).

```
Caller speaks -> browser speech-to-text -> FastAPI brain (nlu -> dialogue -> responses) -> browser text-to-speech
```

## Quick start

### Docker

```bash
docker compose up --build
```

Open http://localhost:8080. Data lives in the `clinic-data` volume (`docker compose down -v` resets it).

### Local development

Backend (Python 3.11):

```bash
cd backend
~/.pyenv/versions/3.11.16/bin/python -m venv .venv   # or: pyenv shell 3.11 && python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload              # http://localhost:8000
```

Frontend (second terminal):

```bash
cd frontend
nvm use stable && npm install && npm run dev         # http://localhost:5173
```

### Browser support

Voice needs **Chrome or Edge** (Web Speech API) and microphone permission; `localhost` counts as a secure context. Other browsers get the text box, which works the same way.

## Demo script

The database is seeded on first start with fake patients. Seed dates are relative to the day the server first starts: "day 1" is the first weekday after that day, "day 2" the weekday after that. Examples below assume you say real weekdays/dates; "tomorrow" works if day 1 is tomorrow.

| Seeded appointment | Ref |
|---|---|
| John Carter, DOB 1985-07-12, Dr Patel, day 1 10:00 | `CLN-JC01` |
| Emily Stone, DOB 1992-02-29, Dr Nguyen, day 1 14:00 | `CLN-ES01` |
| Emily Stone, Dr Patel, day 2 11:00 | `CLN-ES02` |
| Alex Morgan, DOB 1970-01-01, Dr Khan, day 1 15:00 and 15:30 | `CLN-AM01`, `CLN-AM02` |

1. **Book, one sentence:** "Hi, I'd like to book with Dr Patel tomorrow at 2pm, my name is Sara Lee" -> "March 4 1990" -> "yes". You get a reference like `CLN-XXXX`, read out digit by digit.
2. **Change your mind:** start a booking, reach the read-back, say "actually make it 3:30". The read-back repeats with the new time.
3. **Slot taken:** "Book with Dr Khan on day 1 at 3pm" (his 15:00 and 15:30 are taken). The brain offers the 3 nearest free slots; say "the second one".
4. **Cancel by ref:** "Cancel my appointment" -> "CLN-JC01" -> "yes".
5. **Several matches:** "Cancel" -> "Emily Stone" -> "February 29 1992". Two appointments are listed; pick "the first one".
6. **Reschedule:** "Reschedule" -> "CLN-ES02" -> "next Wednesday at 11" -> "yes" (same doctor, same reference).
7. **Safety:** at a read-back say "no please don't book it": nothing is booked. Say "I'm having chest pain" at any time: it tells you to call 911 and ends the call.

## Tests and lint

```bash
cd backend
.venv/bin/pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy app

cd ../frontend
npm test -- --run
npm run lint
npm run build
```

CI (`.github/workflows/ci.yml`) runs the same commands plus `docker compose build`.

## Configuration

Environment variables (see `.env.example`; no secrets):

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_PATH` | `clinic.db` | SQLite file (`/data/clinic.db` in Docker) |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `CLINIC_TIMEZONE` | `America/New_York` | Used for "today", "tomorrow" and seeding |

## API

- `GET /api/health`
- `POST /api/calls` -> `{call_id, reply, decision}` (starts a call, returns the greeting)
- `POST /api/calls/{call_id}/turns` with `{"text": "..."}` -> `{reply, decision, ended}`

Calls idle for 30 minutes expire (404).

## Project structure

```
backend/app/
  clinic.py      doctors, specialties, hours
  nlu.py         text -> intent + entities
  parsing.py     date, time and DOB parsing (stdlib only)
  dialogue.py    state machine and slot filling
  responses.py   reply templates
  scheduling.py  availability, booking, cancelling (SQLite)
  db.py          schema, seed data
  main.py        FastAPI app
backend/tests/   unit, scenario and API tests
frontend/src/    React + TypeScript UI, speech hook, API client
docs/superpowers/  design spec and implementation plan
```
