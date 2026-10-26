# REDELIVER Backend Guide

## What this backend does

The API accepts a text transcript for each caller turn and runs the REDELIVER
dialogue brain. The brain normalizes the transcript, extracts slots, detects
an intent with weighted rules, advances an explicit state machine, and calls
the relevant verification, booking, pickup, or cancellation service.

The repository also includes a React caller frontend. It submits text turns to
these endpoints and renders the returned `reply` and `trace`. Optional
microphone input and spoken replies use browser-native speech APIs; the
backend remains the only application API/service layer and all dialogue and
parcel decisions remain server-side. There is no phone-system integration or
external speech provider.
Runtime scheduling and spoken time prompts use Pakistan Standard Time
(`UTC+05:00`, PKT), without relying on an installed timezone database. Pickup
addresses and recipient names are fictional Pakistan-localized demo data, not
real service locations.

## Start the backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

For macOS/Linux, activate with `source .venv/bin/activate`. The default config
works for local development. Optional values are listed in `.env.example`.
The backend serves interactive OpenAPI docs at `http://localhost:8000/docs`.

## Run the frontend

In a second terminal from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`. In development, Vite
proxies `/api` requests to the backend on port 8000. The frontend speech
controls use browser capabilities; if microphone permission or speech
recognition is unavailable, type turns into the transcript composer. The
backend itself receives only text turns.

## Endpoints

### `GET /health`

Returns `{"status":"ok","version":"1.0.0"}` when the service responds.

### `POST /sessions`

Creates a new conversation and returns HTTP 201:

```json
{
  "session_id": "<generated UUID>",
  "state": "COLLECT_TRACKING_ID",
  "greeting": "Hello. Welcome to REDELIVER..."
}
```

Keep the session ID and send it with each later request.

### `POST /sessions/{session_id}/turns`

Request fields:

| Field | Type | Behavior |
|---|---|---|
| `text` | string, optional | Transcript, maximum 2,000 characters; defaults to empty |
| `silence` | boolean, optional | Marks a silent turn; defaults to `false` |
| `stt_confidence` | number or null, optional | A value below `0.5` causes a repeat prompt |

An empty transcript is handled as silence, not a validation error. The response
contains `reply`, `ended`, and `trace`. The trace includes detected intent,
confidence, extracted slots, and state before/after processing.

Example request:

```json
{
  "text": "RD30000001",
  "stt_confidence": 0.98
}
```

### `GET /sessions/{session_id}`

Returns current state, verification flag, ended flag, collected slots, and
turn history. An unknown ID returns 404.

### `DELETE /sessions/{session_id}`

Marks the session ended and returns 204. The session remains retrievable so
its end state and history can still be inspected. Later turns receive the
session-ended reply.

## Example conversation

The sample parcel `RD12345678` has phone last four digits `1234` and a
`failed_attempt` status. Sample data is fake and stored in `backend/data/`.
Use a fresh session for this sequence:

1. `POST /sessions` and save the returned `session_id`.
2. Submit `{"text":"RD12345678"}`. The assistant reads back the ID.
3. Submit `{"text":"yes"}` to confirm the ID.
4. Submit `{"text":"1234"}` to verify the phone number.
5. Submit `{"text":"where is my parcel"}` to check status.

For rescheduling, say `reschedule`, then give a date and period (for example,
`tomorrow afternoon`), and confirm the offered slot with `yes`. The seeded
next-day morning slot is full; the assistant offers alternatives where
appropriate.

For pickup, say `pick up`, then choose a listed point by number, name, city,
or area and confirm it. The five pickup points are fictional demo addresses in Islamabad, Lahore,
Karachi, Peshawar, and Rawalpindi. Sample recipient names are fictional
Pakistani names. For cancellation, say `cancel`, then confirm with `yes`.

After a status response or completed booking, pickup, or cancellation, the
assistant asks whether you need anything else. Say `yes` to continue or `no` to
end the call.

The importable request sequence is in
`docs/postman/redeliver.postman_collection.json`.

## Configuration

Settings are read from environment variables or `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed browser origins |
| `LOG_LEVEL` | `INFO` | Stdlib logging level |
| `SESSION_TTL_MINUTES` | `30` | Reserved session lifetime setting |
| `MAX_TRACKING_ATTEMPTS` | `3` | Tracking ID retry limit |
| `MAX_PHONE_ATTEMPTS` | `3` | Failed phone checks before parcel lock |
| `MAX_SILENCE_TURNS` | `3` | Consecutive silence turns before ending |
| `MAX_UNKNOWN_TURNS` | `5` | Consecutive unclear turns before asking whether to transfer to a human |
| `DATA_DIR` | `data` | Fake JSON data directory, relative to `backend/` |
| `APP_ENV` | `development` | Environment label in logs |
| `APP_VERSION` | `1.0.0` | Version returned by `/health` |

For local frontend development the Vite proxy keeps requests same-origin, so
the default CORS setting does not need to change. For a deployed frontend
that calls the backend directly, configure `CORS_ORIGINS` for that site and
set the frontend build variable `VITE_API_BASE_URL` to the backend origin.

## Tests

Run from `backend/`:

```bash
python -m pytest tests/ -v
```

The suite covers parsing, intent rules, state transitions, services, API
contracts, and complete caller workflows. The in-memory session and parcel
stores reset when the process restarts.

## Project rules

- Keep the decision brain deterministic and free of LLM calls.
- Keep application APIs and services in the backend; the frontend calls these endpoints and owns presentation only.
- Use fake caller and parcel data only; never commit secrets.
- Inject the Pakistan local clock (UTC+05:00, PKT) for time-dependent behavior.
- Use `threading.Lock` to protect shared in-memory state.
