# VoxDesk

A voice receptionist for **Northline Studio**, a fictional single-chair barbershop. Speak or type to check availability, book a service, change an appointment, cancel it, or ask about the business. The assistant collects missing details, checks the actual calendar, asks for confirmation, persists the result and returns a booking reference.

**The brain is entirely custom deterministic Python code.** No runtime LLM, prompt, model API, embeddings or intent service decides what happens. Browser speech recognition and synthesis handle audio only. No API keys or paid service accounts are required. Use fictional names and demo data only.

- [DESIGN.md](DESIGN.md): architecture, decision rules, state transitions, transaction guarantees, implementation map and test coverage.
- [AI_USAGE.md](AI_USAGE.md): Codex's contribution, mistakes and corrections, authentic token counters, usage logs and screenshot.
- [TASK.md](TASK.md): the unchanged assessment specification.

## Assessment coverage

| Task requirement | Delivered implementation |
| --- | --- |
| A real job from start to finish | Availability, booking, reference-based rescheduling/cancellation, business questions and polite conversation completion |
| Caller speaks, assistant listens and replies | Browser STT → FastAPI → Python brain → structured reply → browser TTS; typed fallback uses the same workflow |
| Own-code brain, no big-model decisions | Ordered intent rules, separate entity grammars, explicit state transitions and catalog-based reply templates |
| Python backend and React/Next.js frontend | FastAPI, Pydantic, SQLAlchemy and SQLite; Next.js, React and TypeScript |
| Messy conversations | Corrections, retained details, ambiguous values, name wrappers, unclear transcripts, reference recovery, interrupted proposals and safe clarification |
| Real operations | Duration-aware calendar checks and persistent transactional writes, revalidated at confirmation |
| Tests and practical engineering | 407 backend cases; 28 production-browser cases; fixed clocks, disposable databases, concurrency/rollback/retry coverage and CI configuration |
| AI-use transparency | Tool/model disclosure, what went wrong, cumulative token snapshots and the original quota screenshot in AI_USAGE.md |

## Prerequisites

- Python **3.11+**; final local validation used **3.13.3**.
- Node.js **22+** and npm; final local validation used **22.15.0 / 10.9.2**.
- Chrome or Edge for the physical voice demo. Browser support and microphone permission still apply; typed input supports every workflow.
- Internet for installing dependencies. Browser speech recognition may also use an online service. The backend and typed workflows run locally after installation.

## Set up and run

Launch the backend from the **repository root**. A fresh database is created automatically; no seed data, account setup or migration command is needed for a fresh checkout.

Windows PowerShell, terminal 1:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

macOS/Linux, terminal 1:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-lock.txt
cp .env.example .env
.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Terminal 2, all platforms:

```bash
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:3000**. Backend health is at **http://127.0.0.1:8000/api/health** and interactive API documentation at **http://127.0.0.1:8000/docs**. To run the production frontend, stop its development server, then run `npm run build` and `npm start` from `frontend/`. Keep the backend running separately.

### Configuration

Defaults work without environment files. Root `.env` configures the backend. Put frontend changes in `frontend/.env.local`; the root `.env` is not Next.js's environment file.

| Variable | Default | Meaning |
| --- | --- | --- |
| `VOXDESK_DATABASE_URL` | `sqlite:///./voxdesk.db` | SQLite database relative to the backend's launch directory |
| `VOXDESK_TIMEZONE` | `Asia/Karachi` | IANA studio timezone; bundled tzdata supports Windows |
| `VOXDESK_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowed frontend origins |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend address used by Next.js; restart/rebuild after changing it |

`backend/requirements-lock.txt` and `frontend/package-lock.json` pin the dependency snapshots. `backend/requirements.txt` declares supported Python ranges. Runtime databases, local environment files, dependencies, browser outputs and builds are ignored by Git.

## Try the complete workflow

Tap the mic for **each turn**, or type these requests. Use an available Monday–Saturday date within 180 days; choose another date if tomorrow is Sunday.

1. “Book a haircut tomorrow at 3 PM.”
2. “Actually, make it 5 PM instead.”
3. “Use the name Alex Example.”
4. Review the service, date, time and name. Say “Yes” or choose **Confirm appointment**.
5. Keep the `NL-XXXXXXXX` reference. “Change the timing for this appointment” asks for a replacement time and keeps the saved date.
6. “4 PM.” Review the proposed move. “Never mind, don't do it, revert the change” discards it and leaves the saved appointment unchanged.
7. “Cancel my confirmed appointment.” Review the cancellation and confirm separately.
8. “Nothing, thank you so much.” The conversation ends without applying any pending proposal.

Also try “Check beard trim availability Friday afternoon”, “What are your prices?”, “Repeat”, “Start over”, an occupied slot and an unsupported request. Accepting an availability offer starts a booking draft; it does not book without a later complete proposal and confirmation. New sessions need an existing appointment's reference; the app never searches for someone by name.

### Supported language and safe limits

The supported English grammar is deliberately bounded and inspectable. Explicit rules suit this small reception job and meet the task's custom-brain constraint. Clarification is the intended response when the code cannot safely establish the caller's meaning.

| Detail | Examples and behavior |
| --- | --- |
| Services | Haircut, beard trim, hair and beard; exclusions such as “haircut without a beard trim” are respected |
| Dates | Today/tomorrow, weekdays/next weekday, “in two days”, `2026-10-28`, “28th of October 2026”, “October twenty-eighth 2026”, `2026 1028` |
| Times | `5 PM`, `17:30`, “five thirty PM”, “half past four PM”, “quarter to five PM”, `5 30 PM`; bare 1–12 requires AM/PM |
| Names | A fictional name when asked, or “Use the name Alex Example”; marked inline names survive unrelated date/time errors and slot conflicts |
| Corrections | “Actually make it Friday”; directional “from 4 PM to 5 PM”; changing one valid field retains other collected details |
| Uncertainty | Multiple dates/times, slash-date ordering, unsupported services and malformed values ask specific questions and invalidate affected authorization |
| Controls | Repeat, restart, business questions, proposal rejection, courtesy and goodbye; “thank you” alone preserves the workflow |

A named date without a year uses the current studio year; a bare weekday includes today and “next” is strictly upcoming. Fully word-spoken years, broad free-form requests and arbitrary recognition errors are not supported. The assistant does not turn “poke it” into “book it” or infer a name from unrelated words. [DESIGN.md](DESIGN.md#custom-python-brain) explains the grammar and context rules.

## Interface

The transcript scrolls independently above a pinned composer. Mic, mute, replay, language and stop-audio controls stay beside typed input. Light/dark themes use warm neutral surfaces; browser preference storage is guarded. The tab title and waveform favicon identify **VoxDesk**.

The sidebar expands from icons to labels and becomes a drawer on phones. **Decision inspector** expands the chat's real intent, matched rule, extracted fields, state, explanation, next action and raw trace. **Appointment** shows empty/draft/saved/cancelled cards, current catalog price, actual saved duration and separate proposed changes. Its management buttons return to the conversation and still require confirmation. **Studio services** is a dedicated catalog page with prices, durations, combo saving, opening hours and service-specific booking handoff.

Two centered suggestions appear above the composer in a new session, disappear after the first submitted turn and stay hidden on reload. New session restores them. Navigation preserves the conversation and unsent draft; availability choices remain usable with the Inspector collapsed.

### Synthetic studio rules

| Service | Duration | Price |
| --- | --- | --- |
| Classic Haircut | 30 minutes | PKR 1,800 |
| Beard Trim | 20 minutes | PKR 900 |
| Haircut + Beard | 50 minutes | PKR 2,500 |

One chair; Monday–Saturday **10:00–19:00**; Sunday closed. The complete service must fit within opening hours. Adjacent appointments may touch, overlaps are rejected, past starts are rejected and bookings are limited to 180 days ahead. Availability uses ten-minute suggestions, while an exact valid start can use another minute. A displayed slot is never a hold.

## Verification

Final repository audit: **2026-10-26, Asia/Karachi**. Validation used the committed application, a separate production build, isolated ports 3011/8011 and disposable fixed-clock test databases. No tests modify the demo database.

| Check | Observed result |
| --- | --- |
| Backend Pytest suite | **407 passed**; one upstream Starlette/httpx deprecation warning |
| Production-browser suite | **28 passed**, using Edge and the real backend; speech APIs/fault scenarios mocked where specified |
| TypeScript from a clean frontend copy before building | Passed |
| Next.js 15.5.28 production build | Passed, including page and favicon generation |
| Frontend formatting | Passed |
| `npm audit --audit-level=high` | **0 reported vulnerabilities** across all severities |
| Python dependency integrity | `pip check`: no broken requirements |
| Source/history credential-pattern check | No matches for the checked private-key/OpenAI/AWS/GitHub patterns; not a complete security audit |
| Assessment and branch | `TASK.md` matches baseline `1e8a7dc`; branch is `candidate-TUAHASHAIKH` |
| CI | Workflow structure and action SHA pins checked locally; remote execution awaits push |

**Physical verification:** the candidate confirmed on 2026-10-26 that the physical voice check and all manual device/conversation scenarios had been completed successfully. This covers the spoken loop, reply separation, correction/confirmation, mute/replay/stop controls, language choices, denied permission/silent or missing microphone recovery, booking changes, navigation and narrow-screen/keyboard checks. This is candidate-reported manual verification; browser/hardware versions and per-utterance recordings were not supplied, and no measured recognition-accuracy percentage is claimed.

The automated coverage map and testing boundaries are in [DESIGN.md](DESIGN.md#validation-and-coverage). After changing the app or device, repeat a spoken booking/correction/confirmation, a discarded reschedule, a separately confirmed cancellation, permission-denial recovery, replay/stop audio, a reload after an uncertain response and a mobile/keyboard pass. Record unexpected behavior with the actual recognition transcript before repairing it.

### Run the checks yourself

From the repository root:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m pip check
```

On macOS/Linux use `.venv/bin/python` in place of `.venv\Scripts\python`.

From `frontend/`:

```bash
npm run format:check
npm run typecheck
npm run build
npm audit --audit-level=high
```

For browser tests, **free ports 3000/8000 and stop unrelated servers first**. The suite launches its own production frontend and fixed-clock disposable backend; it refuses to reuse existing servers or target an unrelated backend.

```bash
npx playwright install chromium
npm run build
npm run test:e2e
```

The default build must target `http://localhost:8000` or `http://127.0.0.1:8000`. With installed Edge, PowerShell can use `$env:PLAYWRIGHT_CHANNEL = 'msedge'` before `npm run test:e2e`. For alternate ports, set `$env:NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8011'` **before building**, then `$env:E2E_FRONTEND_PORT = '3011'` and `$env:E2E_BACKEND_PORT = '8011'` before running. `E2E_FRONTEND_DIR` may point to a separate frontend copy built with the same API target, preserving a running dev build.

## API and retry contract

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Database/backend health, studio timezone, deterministic-brain label |
| GET | `/api/business` | Synthetic catalog, prices, durations, hours and timezone |
| POST | `/api/sessions` | Create persisted conversation |
| GET | `/api/sessions/{id}` | Retrieve its current context and decision |
| POST | `/api/sessions/{id}/turns` | Process an utterance and, only after confirmation, apply a calendar action |
| GET | `/api/availability?service=haircut&day=2026-10-30` | Query real available starts; choose a valid future date |
| GET | `/api/appointments/{reference}` | Retrieve the authoritative synthetic appointment |

```json
{
  "text": "Book a haircut tomorrow at 3 PM",
  "request_id": "unique-request-0001",
  "expected_revision": 0
}
```

Each new turn uses a new request ID and the current revision. **A retry reuses the exact ID, text and expected revision.** The server replays a stored receipt before checking revision, so a lost success response cannot create a second appointment. Reused IDs with different content or stale revisions return 409; invalid input returns 422, absent resources 404 and transient database failures 503. There is no raw calendar-write endpoint that bypasses the brain.

## Limitations and deployment boundary

This is a local assessment application, not an authenticated public booking service. Bind to localhost. References identify synthetic records; they are not secure customer credentials. Browser recognition can be unavailable or process audio through the browser provider; permission and localhost/HTTPS apply. No telephony, continuous/full-duplex listening, notifications, payments, holidays, multiple chairs or customer identity verification is implemented.

Session history is bounded to 100 messages, but sessions and idempotency receipts have no expiry. New session resets the conversation, not saved appointments. Browser storage failure preserves same-tab retries in memory but can prevent recovery after closing/reloading. Connection status reflects the latest API outcome rather than continuous monitoring. SQLite serializes writers with a ten-second lock timeout; schema evolution needs migrations. Current catalog prices are displayed, not archived billing amounts. Before public deployment, add authentication/authorization, privacy/retention controls, rate limits, managed backups, migrations and broader independent conversation/device testing.

## Candidate branch and submission

The original [upstream instructions](https://github.com/savvpro/savvpro-test-voice-agent) require a fork, a `candidate-<github-username>` branch and a PR to upstream `main`. This checkout uses **`candidate-TUAHASHAIKH`** and preserves `TASK.md` unchanged. All implementation and documentation commits are local; no push or PR has been performed by the coding agent.

After reviewing the final changes and authorizing publication:

```bash
git status
git push -u origin candidate-TUAHASHAIKH
```

Push to the candidate's fork, then open a PR with base **`savvpro/savvpro-test-voice-agent:main`**, head **the candidate's fork**, compare **`candidate-TUAHASHAIKH`**, and title **`feat: complete voice-agent assessment`**. Check the resulting remote CI run and submit before the assessment deadline. Remote CI and the PR are the remaining submission steps, not completed evidence.
