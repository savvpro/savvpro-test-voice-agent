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

The brain supports a bounded English grammar. Unclear details trigger a specific question; they do not authorize a booking. Useful examples:

| Caller intent | Supported behavior |
| --- | --- |
| Start a booking | “Make a new booking”, “Can you fit me in for a haircut?”, “I need a hair and beard appointment” |
| Choose a service | “Haircut plus beard” selects the combination; “haircut without a beard trim” selects only the haircut. Alternatives and unsupported positive choices need clarification. |
| Accept availability | “Yes, do it at 4:30 PM” retains the service/date and supplies the time. Clickable available starts also begin a draft. The complete proposal needs a separate confirmation. |
| Repair details | “I already told you, 5 30 PM” or “change from 4 PM to 5 PM” updates the time and retains other fields. Invalid fields stay rejected until individually repaired. |
| Give a name | Use a fictional name alone when asked, or “Use the name Alex Example”. Mark an inline name with “with/for the name …”; instruction words are removed. Names survive other field errors and occupied slots. |
| Change a saved booking | “Change the timing for this appointment” asks for a new time and keeps the saved date. A general “reschedule the appointment” accepts a new date, time, or both. A new session needs its reference; rejected fields stay rejected. |
| Discard a change | “Cancel that change” or “Never mind, don't do it, revert the change” discards the proposal. During a new-booking draft, “cancel it” discards that draft. During rescheduling, “cancel it” asks which target you mean. |
| Cancel a saved booking | “Cancel my confirmed appointment” or “Cancel NL-XXXXXXXX” selects the stored appointment and requires confirmation. |
| End politely | “Nothing, thank you so much” ends without applying pending changes. “Thank you” alone acknowledges you and preserves the current step. |
| Ask for help/status | “Have you booked it?”, “Where can I find the booking reference?”, “Repeat”, “Start over” and “End the conversation” |

Dates support relative days, weekdays, bounded “in two days”, `YYYY-MM-DD`, “28th of October 2026”, “October twenty-eighth 2026”, “2026 October 28”, and numeric `2026 10 28`, `2026 1028`, `20261028`. A named date without a year uses the current business year, with past-date validation. A bare weekday includes today; “next Monday” is strictly upcoming. Incomplete years, invalid dates, weekday/date mismatches and ambiguous numeric ordering need clarification. Years spoken entirely as words remain unsupported.

Times support AM/PM, unambiguous 24-hour values, noon/midnight, “five thirty PM”, “half past four PM”, “quarter past four PM” and “quarter to five PM” (16:45). Bare 1–12 hours require AM/PM. Supply the full time when clarifying. Unsupported offsets/ranges (“twenty to five”, “between four and five”), malformed values (“around 40”), and negated times need an exact replacement. Negated dates also require clarification. The assistant does not guess what a garbled transcript meant; review the displayed interpretation before confirming.

The centered chat is the main workspace. The sidebar starts as an icon rail and can expand to show labels; on phones it opens as a drawer. The labeled **Decision inspector** button on the right expands or collapses the Inspector with a transition; reduced-motion preferences disable animation. **Appointment** in the sidebar opens the current draft or saved receipt, with proposed changes shown separately. On phones, the calendar icon opens that view. Switching views preserves the conversation and unsent input. Available starts stay in the chat even when the Inspector is closed. Successful actions also show a receipt below the latest assistant reply using the confirmed backend details.

**Explore availability** and **Services & pricing** are centered above the message field in a new session. Sending the first message hides them, including after a reload; **New session** brings them back. Typing an unsent draft leaves them visible.

**Studio services** in the sidebar opens a dedicated catalog with prices, durations, the combo saving and opening hours. **Book** starts the selected service in the conversation; dates, times and confirmation still go through the same backend workflow. **Start a conversation** returns to chat and preserves an unsent draft.

**Appointment** shows a centered empty state, a draft as details arrive, or a saved card with status, reference, service, local date/time, customer, duration and catalog price. The empty-state booking shortcut and saved **Reschedule**/**Cancel booking** buttons return to chat and use the normal confirmation flow. Proposed changes remain separate from saved details; cancelled appointments keep their receipt and hide management buttons. The Decision Inspector button appears only in chat; Appointment keeps **Back to conversation**.

Microphone, spoken-reply toggle, **Listen again**, **Speech language** and stop-audio controls live in the chat bar. US, UK and Pakistan English depend on browser support. Tap the mic for each turn; typing restores focus to the input. The theme button switches between warm neutral light/dark palettes and remembers the preference when storage works. A storage warning means the live tab remains usable, but recovery after closing/reloading may be unavailable.

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
npm run format:check
npm run build
```

Browser tests start their own production UI and fixed-clock backend with a disposable database. **Stop the dev server and free ports 3000/8000 first.** Build with the default API URL (`http://localhost:8000` or `http://127.0.0.1:8000`). The runner checks the build's API target before starting; it refuses a different backend to protect unrelated demo data. Install a Playwright browser once:

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

For alternate ports, set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8011` **before building**, then set `E2E_FRONTEND_PORT=3011` and `E2E_BACKEND_PORT=8011` before running tests. `E2E_FRONTEND_DIR` can point to a separate frontend copy built with that API URL, preserving a running development build. These are environment variables; use `$env:NAME = 'value'` in PowerShell. The suite refuses to reuse existing servers.

Browser tests cover connected booking workflows, lost commit responses/retries, storage failures, saved/proposed details, network errors, keyboard focus, selectable slots, 360/390/768-pixel layouts and speech sequencing/replay/failure. Speech APIs and explicit failure scenarios are mocked; normal workflows use the real backend. Actual microphone access, recognition quality and audible output need the [manual checklist](docs/DEMO_CHECKLIST.md). [The conversation test matrix](docs/CONVERSATION_TEST_MATRIX.md) explains coverage and held-out manual checks; executed results are in [progress](docs/PROGRESS.md).

[GitHub Actions](.github/workflows/ci.yml) is configured to run backend tests on Python 3.11/3.13 and frontend format/type/build/audit/browser checks on Node 22. The workflow has not run remotely while publication is on hold.

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
- Sessions/receipts persist without expiry; history is bounded to 100 messages. New session discards the proposal, not stored appointments. Replayed receipts are historical responses; GET returns current state. Tab-storage failure limits reload recovery; a visible warning explains this, and same-tab retries retain the original request ID in memory.
- SQLite serializes writes; lock waits time out after ten seconds and can be retried. Existing schema changes would need migrations before real deployment.

## Assessment submission workflow

Original assessment: [TASK.md](TASK.md). Upstream: https://github.com/savvpro/savvpro-test-voice-agent.

**Publication is on hold at the candidate's request. All audit fixes remain in local commits; no push or submission PR has been made by the coding agent.**

1. Fork upstream and clone **your fork**.
2. Read `TASK.md`. Work on `candidate-<your-github-username>`; this checkout already uses **`candidate-TUAHASHAIKH`**.
3. Run checks, complete the physical voice demo, and attach authentic token logs/screenshots in `AI_USAGE.md`.
4. Review secrets/real-data risks and commit on the candidate branch.
5. When submission is authorized, push the candidate branch to **your fork**.
6. Open a PR with **base repository** `savvpro/savvpro-test-voice-agent`, **base branch** `main`, **head repository** your fork, and **compare branch** `candidate-<your-github-username>`.
7. Use title **`feat: complete voice-agent assessment`** and submit before the deadline.

The coding agent does not push, create a PR, deploy, or perform destructive Git operations without explicit approval. `TASK.md` is preserved unchanged.
