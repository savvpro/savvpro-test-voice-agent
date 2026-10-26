# VoxDesk

An explainable voice receptionist for **Northline Studio**, a fictional single-chair barbershop. Speak or type to book, check availability, reschedule, cancel, or ask about services. A live Decision Inspector shows the actual matched Python rule, extracted entities, state transition, explanation, and next action.

**All runtime decisions are deterministic Python code. No LLM, API key, paid speech service, authentication, or telephone infrastructure is required.** AI-assisted development is disclosed in [AI_USAGE.md](AI_USAGE.md). Use fictional customer names only.

## Features and architecture

- Complete booking with missing-detail questions, contextual corrections, actual availability, and explicit confirmation.
- Duration-aware overlap checks, operating hours, past-date prevention, and a 180-day horizon.
- Rescheduling and cancellation by synthetic reference, each with separate confirmation.
- Browser speech recognition/synthesis, typed fallback, permission/error guidance, and turn separation.
- Persistent sessions, appointments, transaction-safe concurrent writes, and idempotent retries after an uncertain network outcome.
- Responsive dark interface, confirmation controls, booking receipts, and raw decision traces.

```text
Next.js / TypeScript / Tailwind / Lucide
  browser STT → text ── HTTP ──► FastAPI / Pydantic
  browser TTS ◄ reply + trace      │
                                  ├─ ordered intent rules
                                  ├─ deterministic entity grammar
                                  ├─ explicit state machine
                                  └─ booking service → SQLAlchemy → SQLite
```

`backend/app/brain/` contains the custom brain; `bookings.py` owns calendar rules; `db.py` owns persistence/transactions; `api.py` handles REST contracts. `frontend/app/` contains the workspace, and `frontend/lib/` contains typed API and browser voice adapters. See [DESIGN.md](DESIGN.md) for decisions and tradeoffs.

## Prerequisites

- Python **3.11+** (validated locally with 3.13.3).
- Node.js **22+**, npm (validated with Node 22.15.0).
- Chrome or Edge recommended for voice; modern browsers support typed input.
- Internet for dependency installation. Browser speech recognition may also require internet. Backend decision-making and typed conversations run locally after installation.

## Installation and startup

Run the backend from the **repository root**. The database is created automatically; no seeding or migrations are needed for a fresh checkout.

Windows PowerShell, first terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-lock.txt
cp .env.example .env
.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:3000**. API documentation: **http://127.0.0.1:8000/docs**. Health: **http://127.0.0.1:8000/api/health**.

For a production frontend build, stop the dev server, run `npm run build`, then `npm start` in `frontend/`.

### Environment configuration

Defaults work without an environment file. Root `.env` configures the backend; `frontend/.env.local` configures Next.js. Neither should be committed.

| Variable | Default | Purpose |
| --- | --- | --- |
| `VOXDESK_DATABASE_URL` | `sqlite:///./voxdesk.db` | Database relative to backend launch directory |
| `VOXDESK_TIMEZONE` | `Asia/Karachi` | IANA business timezone; tzdata supports Windows |
| `VOXDESK_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Allowed frontend origins, comma separated |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend backend URL; restart/rebuild after changes |

`backend/requirements-lock.txt` and `frontend/package-lock.json` record verified dependency versions. `backend/requirements.txt` declares supported ranges. SQLite files, environments and build artifacts are ignored by Git.

## Demo

Tap the microphone for **each** spoken turn, or type:

1. “Book a haircut tomorrow at 3 PM.”
2. “Actually, make it 5 PM instead.”
3. “Alex Example.”
4. Review the proposal; say “Yes” or click **Confirm appointment**.
5. Keep the `NL-XXXXXXXX` reference from the booking card.
6. “Reschedule NL-XXXXXXXX Friday at 4 PM.” Then confirm.
7. “Cancel NL-XXXXXXXX.” Then confirm cancellation.

Choose a Monday–Saturday date within 180 days. If tomorrow is Sunday or a slot is taken, choose another day/time. Also try “Check beard trim availability Friday afternoon”, “What are your prices?”, “Repeat”, “Start over”, and “Order a pizza”.

Time expressions such as “at five”, “five thirty”, and “half past four” require AM/PM clarification. Reply with the **full** time, for example “five thirty PM”. Dates support today, tomorrow, day after tomorrow, weekdays, next weekday, and `YYYY-MM-DD`. A bare weekday is the nearest match including today; “next Monday” is the upcoming Monday strictly after today. Conflicting values and numeric slash dates are clarified. Month-name dates and unrestricted English are outside this small grammar. Supply a fictional name as a separate answer to the name question.

Northline Studio opens **Monday–Saturday 10:00–19:00**, with one chair:

| Service | Duration | Synthetic price |
| --- | --- | --- |
| Classic Haircut | 30 minutes | PKR 1,800 |
| Beard Trim | 20 minutes | PKR 900 |
| Haircut + Beard | 50 minutes | PKR 2,500 |

## Testing

From the repository root:

```powershell
.\.venv\Scripts\python -m pytest
```

On macOS/Linux use `.venv/bin/python -m pytest`. Tests use fixed clocks and disposable databases, never the demo database.

Frontend:

```bash
cd frontend
npm run typecheck
npm run build
```

Browser tests start their own production UI and fixed-clock backend. **Stop servers on ports 3000/8000 first** and build with the default API URL. Install a Playwright browser once:

```bash
cd frontend
npx playwright install chromium
npm run build
npm run test:e2e
```

Or use installed Edge in PowerShell:

```powershell
$env:PLAYWRIGHT_CHANNEL = 'msedge'
npm run test:e2e
```

Browser tests use the real backend for booking/corrections, rescheduling/cancellation, a lost response after commit, unsupported voice fallback, mobile overflow, and voice sequencing. Only the speech adapter test mocks browser speech. Actual microphone access, recognition quality and audible output need the [manual checklist](docs/DEMO_CHECKLIST.md). Executed results and remaining limits are in [progress](docs/PROGRESS.md).

## REST API

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | `/api/health` | Backend/database health |
| GET | `/api/business` | Catalog, timezone and hours |
| POST | `/api/sessions` | Create persisted conversation |
| GET | `/api/sessions/{id}` | Retrieve context and decision |
| POST | `/api/sessions/{id}/turns` | Submit utterance |
| GET | `/api/availability?service=haircut&day=2026-10-30` | Real slots; use a future date |
| GET | `/api/appointments/{reference}` | Retrieve synthetic booking |

```json
{
  "text": "Book a haircut tomorrow at 3 PM",
  "request_id": "unique-request-0001",
  "expected_revision": 0
}
```

Use a new request ID and the current revision for each utterance. **Retries reuse the exact body and ID.** Responses include reply, context, decision, available slots, and appointment when applicable. Stale revisions/reused IDs with different bodies return 409, invalid input 422, absent resources 404, and transient database failures 503 without a success claim. All appointment writes go through confirmation; no raw write endpoint bypasses the brain.

## Browser compatibility and limitations

- SpeechRecognition has [limited browser availability](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition). Chrome/Edge are recommended; platform policies may still disable it. Typed input supports every workflow.
- Microphone access needs permission and localhost/HTTPS. Browser speech services may process audio remotely; no paid credentials are configured. Use synthetic information.
- Recognition is aborted before synthesis; the mic stays disabled while speaking. There is no automatic restart or full-duplex streaming. See [MDN recognition stop](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition/stop) and [synthesis cancel](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/cancel).
- Local assessment demo: no authentication, customer identity verification, privacy governance, notifications, payments, holidays, staff selection or multiple chairs. Bind to localhost. References are identifiers, not secure credentials.
- Availability suggestions use a ten-minute grid; an exact valid start may use another minute. Availability is never a hold and is rechecked at confirmation.
- Sessions/receipts persist without expiry; history is bounded to 100 messages. New session discards the proposal, not stored appointments. Replayed receipts are historical responses; GET returns current state.
- SQLite serializes writes; lock waits time out after ten seconds and can be retried. Existing schema changes would need migrations before real deployment.

## Assessment submission workflow

Original assessment: [TASK.md](TASK.md). Upstream: https://github.com/savvpro/savvpro-test-voice-agent.

1. Fork upstream and clone **your fork**.
2. Read `TASK.md`. Work on `candidate-<your-github-username>`; this checkout already uses **`candidate-TUAHASHAIKH`**.
3. Run checks, complete the physical voice demo, and attach authentic token logs/screenshots in `AI_USAGE.md`.
4. Review secrets/real-data risks and commit on the candidate branch.
5. When submission is authorized, push the candidate branch to **your fork**.
6. Open a PR with **base repository** `savvpro/savvpro-test-voice-agent`, **base branch** `main`, **head repository** your fork, and **compare branch** `candidate-<your-github-username>`.
7. Use title **`feat: complete voice-agent assessment`** and submit before the deadline.

The coding agent does not push, create a PR, deploy, or perform destructive Git operations without explicit approval. `TASK.md` is preserved unchanged.
