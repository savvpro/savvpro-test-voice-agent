# REDELIVER — Voice Parcel Support

REDELIVER is a Pakistan-localized voice-assistant prototype for missed parcel deliveries. A caller can confirm a parcel, verify identity, check delivery status, reschedule delivery, choose a collection point, cancel a delivery, ask for an explanation, and request a human-agent transfer. The product includes a public-facing landing page, a dedicated call experience, and an operations dashboard.

This repository is a prototype with fictional parcel records and in-memory state. It is not connected to a courier network, telephony provider, production database, or human-agent queue. Do not enter real customer information.

## Demo

**Demo video URL:** [Open the REDELIVER demo video](https://drive.google.com/file/d/1XVjrna7HK4EXGkwDucubu-gc64AEVIAy/view?usp=sharing)

The embedded preview is muted so it can play on hover without unexpectedly producing sound. Hover playback depends on the Markdown host permitting the video element and its event handlers. GitHub sanitizes some inline HTML behavior; there the native player controls and the video link are the fallback. When replacing the placeholder, use a publicly accessible direct video URL (MP4/WebM) or a host that provides an embeddable video player. A normal Google Drive share-page URL may need to be converted to an embeddable/direct video URL.

<video src="https://example.com/redeliver-demo.mp4" poster="frontend/src/assets/hero.png" controls muted playsinline preload="none" onmouseover="this.play()" onmouseout="this.pause()" style="max-width: 100%; height: auto;">
  Your Markdown viewer cannot embed video. <a href="https://example.com/redeliver-demo.mp4">Open the demo video</a>.
</video>

## Contents

- [Product behavior](#product-behavior)
- [Architecture and AI boundary](#architecture-and-ai-boundary)
- [Repository layout](#repository-layout)
- [Requirements](#requirements)
- [Local setup](#local-setup)
- [Try a complete call](#try-a-complete-call)
- [Backend guide](#backend-guide)
- [Frontend guide](#frontend-guide)
- [HTTP API](#http-api)
- [Configuration](#configuration)
- [Data and privacy](#data-and-privacy)
- [Testing and quality checks](#testing-and-quality-checks)
- [AI-assisted development](#ai-assisted-development)
- [Project documentation](#project-documentation)
- [Current limitations](#current-limitations)

## Product behavior

A typical conversation follows this flow:

1. The assistant asks for a tracking ID in the form `RD` followed by eight digits.
2. It reads the ID back and asks the caller to confirm it.
3. It asks for the last four phone-number digits and verifies them against the sample parcel record.
4. It presents actions allowed for that parcel's current status.
5. It gathers and confirms a delivery slot, pickup location, or cancellation when required.
6. After an action or status explanation, it asks whether the caller needs anything else. It only ends after the caller declines or explicitly says goodbye.

The dialogue uses a deterministic backend state machine, weighted keyword and pattern matching, a transcript normalizer, and slot extraction. It accounts for speech recognition artifacts such as number words, repeated digits, filler words, and common spoken variants of “R D.” When input is unclear, it can ask for a repeat, offer a human-agent transfer for confirmation, and handle silence. Parcel status rules restrict which actions are available.

The experience uses fictional locations in Islamabad, Lahore, Karachi, Peshawar, and Rawalpindi. Dates and times use Pakistan Standard Time (UTC+05:00), and browser voice features request Pakistani English (`en-PK`) where the browser supports it.

## Architecture and AI boundary

```text
Browser microphone or typed transcript
        │
        ▼
React frontend ─── HTTP/JSON ───► FastAPI session API
        │                              │
        │                              ▼
        │                     Normalize transcript
        │                     Extract intent/slots
        │                     Run dialogue state machine
        │                     Call backend services
        │                     Read/update in-memory data
        │                              │
        ◄──── reply + trace JSON ──────┘
        │
        ├── Render transcript and decision trace
        └── Optional browser speech synthesis of backend reply
```

**The running REDELIVER assistant does not call an LLM or generative AI service.** Python code decides the intent, missing information, next prompt, allowed action, and state transition. The API returns a reply and trace; the frontend presents them. No API keys or model credentials are required for local use.

Optional voice input and output are browser features, not AI decision services:

- `SpeechRecognition` / `webkitSpeechRecognition` supplies a text transcript where available. The frontend sends that text to the backend for every turn.
- `speechSynthesis` speaks the reply returned by the backend. The browser chooses a Pakistani English voice when one is available and otherwise falls back to an English voice.
- Typed replies remain available if voice recognition or microphone permission is unavailable.
- The WebGL hero/call visualizer samples microphone input while listening. Browser speech synthesis does not expose its playback stream to the page, so its “speaking” animation is driven by the assistant speaking state rather than measured output audio.

## Repository layout

```text
.
├── README.md
├── TASK.md                         # Original task and project constraints
├── DESIGN.md                       # Product design, dialogue brain, boundaries
├── AI_USAGE.md                     # AI tools and user-provided usage snapshot
├── docs/
│   ├── BACKEND_GUIDE.md            # Backend setup, behavior, and API examples
│   ├── PLAN.md                     # Planned architecture and implementation steps
│   ├── PROGRESS.md                 # Completed work and recorded test results
│   └── postman/
│       └── redeliver.postman_collection.json
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI routes and dependency providers
│   │   ├── brain/                  # Normalization, intent, extraction, state machine
│   │   ├── core/                   # Settings and structured logging
│   │   ├── data/                   # Interfaces, loader, in-memory repositories
│   │   ├── models/                 # Pydantic data and API schemas
│   │   └── services/               # Verification, booking, pickup, cancellation
│   ├── data/                       # Fictional parcel, slot, and pickup-point JSON
│   ├── tests/                      # Unit, API, edge, and end-to-end scenario tests
│   └── requirements.txt
└── frontend/
    ├── public/                     # Static icons and favicon
    ├── src/
    │   ├── components/             # SiteHome and WebGL VoiceVisualizer
    │   ├── hooks/                  # Visual effects/reveal hook
    │   ├── services/               # Centralized backend API client
    │   ├── AppNext.jsx             # Landing, call experience, dashboard logic
    │   └── AppNext.css             # Product, call, dashboard, and responsive styles
    ├── package.json
    ├── package-lock.json
    └── vite.config.js
```

## Requirements

- Python 3.11 or later is recommended for the backend.
- Node.js and npm versions supported by the Vite version pinned in `package-lock.json`.
- A modern browser. Chrome or Edge generally provide the most consistent browser speech API support, but typed input works without it.
- Microphone access for voice input. The browser may require `localhost` or HTTPS to grant access.

## Local setup

Run the backend and frontend in separate terminals. Commands below use PowerShell from the repository root; equivalent macOS/Linux activation is shown below.

### 1. Create and activate the Python environment

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, either allow local activation in your own terminal policy or use the interpreter directly:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS/Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. Start the backend API

From `backend/`, with the virtual environment active:

```powershell
uvicorn app.main:app --reload --port 8000
```

Useful URLs:

- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Interactive OpenAPI/Swagger docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Alternative ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

The API listens on port `8000` by default in this command. Leave this terminal running.

### 3. Install and start the frontend

Open a second terminal from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite, usually [http://localhost:5173](http://localhost:5173). Vite proxies browser requests from `/api` to `http://127.0.0.1:8000` during development. Keep both development servers running while using the app.

For macOS/Linux the same commands apply from `frontend/`. `npm ci` uses the committed lockfile for repeatable dependency installation.

### 4. Confirm the local services are reachable

Visit `/health` in a browser or run:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

You should receive a small JSON response with `status: ok` and the configured application version. The frontend should show the API as connected. If it does not, confirm the backend terminal is still running on port 8000 and reload the page.

## Try a complete call

1. Open the frontend and choose **Try the voice demo** or **Voice demo**.
2. Select **Start voice call**. The backend creates a new session and returns its greeting.
3. Use the sample parcel `RD12345678`; confirm it when asked.
4. The matching sample phone last four digits are `1234`.
5. Once verified, try **check status**, **reschedule**, **pick up**, or **cancel**. Follow the assistant prompts and confirm any proposed action.
6. After completion, answer the “anything else?” prompt with `yes` to continue or `no` to end.

Example records are deliberately fake. Rescheduling availability depends on the runtime date and seeded slot template. The sample `RD12345678` is a failed-attempt parcel; other examples in `backend/data/parcels.json` represent different statuses and allowed workflows.

### Browser voice controls

- Press **MIC** and grant microphone permission to use browser speech recognition.
- Speak naturally; recognized text appears in the conversation and is sent to the backend.
- The microphone button toggles listening. A typed response can be entered in the composer at any time.
- **VOICE ON/OFF** controls browser speech synthesis of backend replies. **REPLAY** repeats the most recent assistant response; **STOP SPEAKING** interrupts it.
- The frontend does not send audio recordings to the backend; the API receives text, a silence flag, and optionally a speech-recognition confidence score.

## Backend guide

### Responsibilities and request lifecycle

The FastAPI backend is the source of truth for all application behavior:

1. `app/api/routes/sessions.py` validates the request and obtains the current session, repository, settings, and Pakistan-local clock through dependencies.
2. `app/brain/normalizer.py` produces normalized intent and digit text from the caller transcript.
3. `app/brain/slot_filler.py` and `app/brain/extractor.py` extract only the slots relevant to the current state (tracking ID, phone suffix, date/period, or pickup point).
4. `app/brain/intent_detector.py` scores weighted whole-word phrases and regular-expression patterns. State-aware priority and disambiguation rules reduce incorrect matches in confirmations and follow-up states.
5. `app/brain/state_machine.py` applies cross-cutting rules and explicit state handlers. It calls backend services and builds a decision trace.
6. `app/services/` performs identity verification, slot booking/rebooking, pickup selection, and cancellation.
7. The endpoint returns the assistant reply, session end flag, and trace as JSON. The frontend does not independently implement these decisions.

### Dialogue states

The explicit states in `backend/app/models/session.py` are:

- `GREETING` — initial state constant; a new session currently starts in `COLLECT_TRACKING_ID` after adding the greeting.
- `COLLECT_TRACKING_ID`, `CONFIRM_TRACKING_ID` — collect and verify the spoken/typed tracking identifier.
- `VERIFY_PHONE` — request and check the last four phone digits; repeated failure can lock that parcel.
- `CHOOSE_ACTION` — select an action allowed by the parcel status.
- `DELIVER_STATUS` — report parcel status and, when needed, explain statuses such as a failed attempt.
- `COLLECT_DATE`, `COLLECT_PERIOD`, `CONFIRM_SLOT` — gather a date/window, check availability, and confirm a reschedule.
- `COLLECT_PICKUP_POINT`, `CONFIRM_PICKUP` — present pickup choices, resolve a city/name/number/alias, and confirm the choice.
- `CONFIRM_CANCEL` — obtain confirmation before cancellation.
- `ANYTHING_ELSE` — ask whether the caller needs another service; the caller's answer determines whether to continue or end.
- `END` — terminal state.

The brain also handles repeat requests, low-confidence speech recognition, silence limits, unclear-turn limits, explicit goodbye, and human-agent handoff. The handoff offer is confirmed by the caller before the assistant says it is transferring; this prototype has no connected human queue.

### Backend modules

| Area | Main files | Responsibility |
|---|---|---|
| API and wiring | `app/main.py`, `app/api/routes/`, `app/api/dependencies.py` | App factory, CORS, route registration, dependency injection, cached in-memory services, PKT clock |
| Brain | `app/brain/normalizer.py`, `extractor.py`, `date_parser.py`, `intent_detector.py`, `slot_filler.py`, `state_machine.py`, `constants.py` | Deterministic text processing, intent rules, slots, prompts, and state transitions |
| Services | `app/services/verification.py`, `booking.py`, `pickup.py`, `cancellation.py` | Business actions called by the state machine |
| Data | `app/data/loader.py`, `interfaces.py`, `repository.py` | Load/validate fake JSON, generate delivery windows, and read/update in-memory data |
| Models | `app/models/api.py`, `parcel.py`, `session.py` | Pydantic API contracts, parcel/status types, session slots/history/traces |
| Runtime config | `app/core/config.py`, `logging.py` | Environment settings and structured JSON logs |

### Deterministic brain details

- The normalizer has an intent-oriented pass and a digit-oriented pass so number words remain meaningful for intent detection while tracking/date extraction can use digits.
- Tracking extraction supports spoken “R D” variants and digit grouping. Phone extraction avoids reusing tracking-ID digits as the phone suffix.
- Date parsing resolves relative dates against an injected PKT clock and recognizes delivery periods. Slots are state-gated to avoid treating unrelated numbers as dates or phone digits.
- Intent scoring combines configured phrase/pattern weights, caps scores, applies a confidence threshold and ambiguity margin, and uses state-specific priority for affirmative/negative confirmations.
- Parcel status rules gate actions. Booking checks capacity and dates; rescheduling and cancellation release an existing slot when appropriate.
- The decision trace reports state before/after, intent and confidence, runner-up intent, extracted slots, and a rejection reason when the request could not be accepted.

### Data and concurrency

- `backend/data/parcels.json` contains fictional tracking IDs, phone suffixes, recipient labels, and statuses.
- `backend/data/pickup_points.json` contains five fictional Pakistan locations, aliases, opening days, and hours.
- `backend/data/slots.json` is a capacity/prebooking template. At runtime, the backend makes a seven-day window with morning, afternoon, and evening periods (21 slots total) relative to the injected clock.
- The repository and session store are in-memory. A restart resets sessions, booking mutations, phone attempt counters, and locks.
- A `threading.Lock` protects repository mutations. Session locks serialize turns for a given session; the state machine should not process concurrent turns for the same call simultaneously.

## Frontend guide

### Responsibilities

The frontend is a React 19 + Vite application. It owns the website, transcript layout, local interaction state, browser speech controls, theme preference, animations, and presentation of the backend response. It does **not** decide parcel eligibility, match intents, verify identity, select a time slot, or mutate parcel records.

- `src/AppNext.jsx` wires health/session calls to the call flow and dashboard.
- `src/components/SiteHome.jsx` renders the landing page.
- `src/components/VoiceVisualizer.jsx` draws the orb and audio waveform, reading microphone amplitude through Web Audio while listening. It falls back to CSS without WebGL and respects reduced-motion preferences.
- `src/services/redeliverApi.js` centralizes `fetch`, JSON headers, HTTP errors, and the configured API base URL.
- `src/hooks/useFx.jsx` provides scroll reveal behavior and motion cleanup.
- `src/AppNext.css` contains site, call, dashboard, responsive, and visualizer styles.
- `src/main.jsx` is the Vite/React entry point.

### Pages and client behavior

- **Landing page:** product overview, Pakistan service context, workflow sections, and an entry point to the voice experience.
- **Call page (`#voice`):** start/end a call, read the live transcript, enter text, use the microphone, replay/interrupt speech, toggle voice replies, and see the backend decision trace.
- **Dashboard (`#dashboard`):** live backend status and current-session state/history. It intentionally does not invent historical analytics or administrative features for which this API has no data.
- **Theme and voice preferences:** presentation/browser preferences only; they do not affect backend business rules.
- **API wrapper:** by default calls `/api`. In Vite development, that path is proxied to the backend. For a separately deployed frontend, set `VITE_API_BASE_URL` to the backend origin at build time.

## HTTP API

The interactive OpenAPI schema is available at `http://127.0.0.1:8000/docs` when the backend is running.

| Method | Path | Success | Purpose |
|---|---|---:|---|
| `GET` | `/health` | `200` | Check service and application version |
| `POST` | `/sessions` | `201` | Create a session and return ID, starting state, greeting |
| `POST` | `/sessions/{session_id}/turns` | `200` | Submit one text/silence turn and receive reply + trace |
| `GET` | `/sessions/{session_id}` | `200` | Read state, verification, slots, end flag, and history |
| `DELETE` | `/sessions/{session_id}` | `204` | Mark the session ended and retain it for history lookup |

### Example: use the API without the frontend

Start a session:

```powershell
$session = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/sessions -ContentType 'application/json' -Body '{}'
$session
```

Submit a turn (replace the ID with the returned session ID):

```powershell
$body = @{ text = 'RD12345678'; stt_confidence = 0.98 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/sessions/$($session.session_id)/turns" -ContentType 'application/json' -Body $body
```

The turn body accepts `text` (up to 2,000 characters), `silence` (boolean), and optional `stt_confidence`. An empty transcript is handled as silence. Confidence below `0.5` triggers a repeat prompt. If the browser reports an unusable zero confidence, the frontend omits it so the backend default is used.

A turn response has this shape:

```json
{
  "reply": "I heard R. D. 1. 2. 3. 4. 5. 6. 7. 8. Is that correct?",
  "ended": false,
  "trace": {
    "intent": null,
    "intent_confidence": null,
    "runner_up": null,
    "runner_up_confidence": null,
    "slots_extracted": {"tracking_id": "RD12345678"},
    "state_before": "COLLECT_TRACKING_ID",
    "state_after": "CONFIRM_TRACKING_ID",
    "rejection_reason": null
  }
}
```

Unknown session IDs return `404`. Session history can be read before/after ending. See [docs/BACKEND_GUIDE.md](docs/BACKEND_GUIDE.md) for a longer request walkthrough and [the Postman collection](docs/postman/redeliver.postman_collection.json) for ready-to-import requests.

## Configuration

Backend settings come from process environment variables or `backend/.env` (Pydantic Settings). Defaults work for local frontend development.

| Setting | Default | Purpose |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed browser origins for direct cross-origin requests |
| `LOG_LEVEL` | `INFO` | Python logging threshold; emitted messages use structured JSON formatting |
| `SESSION_TTL_MINUTES` | `30` | Configured session lifetime setting; sessions are currently held in an in-memory store |
| `MAX_TRACKING_ATTEMPTS` | `3` | Tracking-ID retry limit |
| `MAX_PHONE_ATTEMPTS` | `3` | Phone verification failure limit before a parcel is locked |
| `MAX_SILENCE_TURNS` | `3` | Consecutive silence limit |
| `MAX_UNKNOWN_TURNS` | `5` | Unclear-turn limit before the assistant offers human transfer |
| `DATA_DIR` | `data` | Backend JSON data folder; relative paths resolve from `backend/` |
| `APP_ENV` | `development` | Runtime environment label in startup logs |
| `APP_VERSION` | `1.0.0` | API version returned by `/health` |

To customize local values, create `backend/.env` (do not commit secrets):

```dotenv
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
LOG_LEVEL=INFO
APP_ENV=development
APP_VERSION=1.0.0
MAX_TRACKING_ATTEMPTS=3
MAX_PHONE_ATTEMPTS=3
MAX_SILENCE_TURNS=3
MAX_UNKNOWN_TURNS=5
DATA_DIR=data
```

For a directly hosted frontend, set `CORS_ORIGINS` to its exact origin and build the frontend with `VITE_API_BASE_URL=https://your-api-host.example`. Do not include `/api` unless the deployed backend is actually mounted below that prefix. Keep `.env` files and credentials out of version control.

## Data and privacy

All parcel records, recipient names, phone suffixes, and pickup addresses are fictional testing fixtures. The application is intended for local evaluation. The backend keeps state in process memory, does not persist records to a database, and loses active sessions and mutations on restart. The API accepts text transcripts; browser microphone capture is not uploaded as an audio file. Structured backend logging is designed to avoid logging caller transcript contents and phone digits. Do not put real personal data into demo calls or logs.

## Testing and quality checks

The backend suite covers normalization, tracking/phone/date extraction, intent scoring, slot filling, state transitions, service rules, API dependencies, endpoints, edge cases, and multi-turn workflows. Run from `backend/`:

```powershell
python -m pytest tests/ -v
```

Optional coverage report:

```powershell
python -m pytest tests/ --cov=app --cov-report=term-missing
```

Python lint (Ruff):

```powershell
ruff check .
```

Frontend checks run from `frontend/`:

```powershell
npm run lint
npm run build
```

The latest result recorded in `docs/PROGRESS.md` is **491 backend tests passed, 2 warnings, 90% total coverage** at the time that progress entry was written. The warnings documented there concern Pydantic's lock type and a Starlette/httpx deprecation; consult the progress document for details and rerun the suite for the current checkout.

## AI-assisted development

Antigravity and OpenAI Codex were used as development assistants for code implementation, debugging, review, and documentation. Their role was software-development assistance; **neither is a runtime dependency or called by the REDELIVER assistant**. The live dialogue decisions remain explicit Python rules, and there are no LLM SDKs or API keys required to run the project. Browser speech recognition and speech synthesis are optional built-in browser capabilities and do not choose the assistant's actions.

The following usage values came from a user-provided Codex snapshot and a requested six-times Antigravity estimate. They are historical estimates, not measurements of this repository's exact token cost:

| Tool | Session/context snapshot | Usage note |
|---|---|---|
| Codex | Session `01a1789e-7908-7630-819f-1ba74670ec5e`; `184,237 / 258K` used; `29%` context left | Snapshot supplied by the project owner |
| Antigravity | Estimated `1,105,422 / 1,548,000` used, scaled 6× from the supplied Codex values | Estimate only; not independently measured |

See [AI_USAGE.md](AI_USAGE.md) for how tools were used, reviewed corrections, and the original usage notes.

## Project documentation

- [TASK.md](TASK.md) — assignment goals and project constraints.
- [DESIGN.md](DESIGN.md) — product behavior, deterministic brain, and frontend/backend separation.
- [docs/PLAN.md](docs/PLAN.md) — planned architecture and implementation sequence.
- [docs/PROGRESS.md](docs/PROGRESS.md) — completed steps, decisions, test records, and known warnings.
- [docs/BACKEND_GUIDE.md](docs/BACKEND_GUIDE.md) — backend-specific setup, API walkthrough, and configuration.
- [frontend/README.md](frontend/README.md) — frontend setup, speech behavior, and page/API mapping.
- [AI_USAGE.md](AI_USAGE.md) — development AI tool record and token-usage notes.
- [docs/postman/redeliver.postman_collection.json](docs/postman/redeliver.postman_collection.json) — importable API request collection.

## Current limitations

- No telephony, SMS, courier network, production database, authentication, or live agent handoff is connected.
- Demo records are static fictional JSON. Runtime edits are in-memory and disappear when the backend restarts.
- Browser speech recognition support, language packs, voice availability, and microphone permissions depend on the browser and operating system. Text input remains available.
- Browser speech synthesis output cannot currently drive an actual output-audio analyser; speaking animation follows the app's speaking state.
- The dashboard shows current backend/session data only. There is no historical analytics or multi-user administration API.

