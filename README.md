# Harbor Lights Bistro — Voice Booking Assistant

This is a small but complete **phone-style table booking** assistant for a fictional restaurant called **Harbor Lights Bistro**. You talk to it (mic) or type. It books a dinner table, shows you every decision it made, and stores the booking in SQLite so a restart does not wipe the night’s list.

I built this as **Work 2** of the SAVV Pro technical take-home (voice agent). The other option was a statement categorizer. I picked voice because hiring teams in 2025–2026 care a lot about conversational agents, state machines you can explain, and a UI that proves the brain is not a black box. A CSV-upload categorizer is fine work; it just looks more like every other take-home.

**Important for reviewers / for me submitting later**

- Fork, branch, push, and PR are **manual steps I will do myself** on GitHub. Nothing in this folder was pushed from the build machine.
- Branch name when I submit: `candidate-<my-github-username>`.
- This README is the runbook for the app. The original assessment `README.md` / `TASK.md` on GitHub still own the formal submission rules.

---

## Table of contents

1. [What this is](#what-this-is)
2. [Why a voice agent (and why this restaurant)](#why-a-voice-agent-and-why-this-restaurant)
3. [Free stack — exact pieces](#free-stack--exact-pieces)
4. [What you get when it runs](#what-you-get-when-it-runs)
5. [Folder map (file by file)](#folder-map-file-by-file)
6. [Prerequisites](#prerequisites)
7. [Git on this Windows machine (`D:\Softwares\Git`)](#git-on-this-windows-machine-dsoftwaresgit)
8. [Setup on Windows (step by step)](#setup-on-windows-step-by-step)
9. [Batch files — what each one does](#batch-files--what-each-one-does)
10. [Run without batch files](#run-without-batch-files)
11. [Docker Compose](#docker-compose)
12. [How the dialogue brain works (short)](#how-the-dialogue-brain-works-short)
13. [How to demo a booking](#how-to-demo-a-booking)
14. [Messy caller cases worth trying](#messy-caller-cases-worth-trying)
15. [Admin panel (password on screen)](#admin-panel-password-on-screen)
16. [API endpoints](#api-endpoints)
17. [Tests](#tests)
18. [Design / AI usage docs](#design--ai-usage-docs)
19. [Screenshots (01–25)](#screenshots-0125)
20. [Troubleshooting](#troubleshooting)
21. [Submission checklist (you do GitHub)](#submission-checklist-you-do-github)
22. [Local “pro” vs cloud (honest)](#local-pro-vs-cloud-honest)
23. [Env knobs](#env-knobs)

---

## What this is

A two-process local app:

| Process | Role | Default URL |
| --- | --- | --- |
| FastAPI backend | Dialogue engine, SQLite, admin APIs, health, rate limit | http://localhost:8000 |
| Vite + React frontend | Talk UI, mic/TTS, decision trace, admin hash-route | http://localhost:5173 |

Speech recognition and speech synthesis stay **inside the browser** (Web Speech API). The server only ever sees **text** on `POST /api/turn`. That means:

- no audio uploads
- no speech vendor account
- typed input is a first-class path, not an afterthought

Bookings land in `backend/data/bookings.db`. Soft-cancel sets `status=cancelled` so the table frees up; restore flips it back if the table is still free.

---

## Why a voice agent (and why this restaurant)

SAVV Pro offered two tracks. I chose the voice agent because:

1. **Market signal** — voice + tool-using agents are what interviews keep asking about.
2. **Explainable brain** — a state machine with a visible decision trace is easier to defend than “we called an LLM.”
3. **Demoable in 2 minutes** — type one sentence, confirm, show ticket + admin row.
4. **Same professionalism bar** — README, DESIGN, AI_USAGE, tests — without looking like a generic CRUD upload app.

**Harbor Lights Bistro** is fictional on purpose. Dinner service is fixed (5:00 PM–9:00 PM, half-hour slots, party 1–20, eight fake tables). Narrow rules keep the parser honest and the tests tight.

---

## Free stack — exact pieces

No API keys. No paid speech. No LLM at runtime.

| Piece | Concrete choice | Notes |
| --- | --- | --- |
| Language (API) | Python 3.10+ | 3.11/3.12 fine |
| Web framework | FastAPI + Uvicorn | lifespan startup (not deprecated `on_event`) |
| Brain | Hand-written state machine | `dialogue.py` + `parser.py` |
| Dates | `python-dateutil` | “Friday”, “tomorrow”, etc. |
| DB | SQLite via stdlib `sqlite3` | file under `backend/data/` |
| Rate limit | In-memory sliding window | per IP + session; off under pytest |
| STT | `webkitSpeechRecognition` / `SpeechRecognition` | Chrome / Edge |
| TTS | `window.speechSynthesis` | browser voices |
| UI | Vite + React (JSX) | dark theme |
| Admin auth | Shared password header | default `admin` — demo grade |
| Containers | Docker Compose + nginx for static UI | optional |
| Windows DX | `RUN_APP.bat`, `run.bat`, `test.bat`, `run-docker.bat` | double-click |

You do **not** need OpenAI, Anthropic, Gemini, Deepgram, ElevenLabs, AssemblyAI, Whisper cloud, Twilio, SendGrid, or Redis for this submission.

---

## What you get when it runs

- Greeting turn on load (session id created client-side).
- Green / red **API** pill (health poll).
- Mic button + text box.
- Live **decision trace** (state before/after, intent, slots, action, notes).
- **Confirmation ticket** after a successful book (id, restaurant, when, party, table).
- Fake notification line appended to `backend/data/notifications.log` (never really sent).
- **Admin** at `#/admin` with password banner **Demo password: `admin`**, stats, seed, CSV, cancel/restore, open slots.
- Offline banner if the API is down.

---

## Folder map (file by file)

```text
savvpro-test-voice-agent-SUBMIT/          ← submit this folder (flat, no nesting)
├── README.md                             ← this file
├── TASK.md                               ← original assessment task copy
├── DESIGN.md                             ← architecture + state diagram notes
├── AI_USAGE.md                           ← what AI helped with / what it did not
├── .env.example                          ← copy to .env if you change knobs
├── .gitignore
├── .dockerignore
├── Makefile                              ← make test / make up helpers
├── docker-compose.yml
├── RUN_APP.bat                           ← Windows: API + UI + open browser
├── run.bat                               ← thin alias → RUN_APP.bat
├── test.bat                              ← Windows: pytest
├── run-docker.bat                        ← Windows: docker compose up --build
├── docs/
│   ├── GIT_BASH_WINDOWS_SETUP.md         ← PATH + Git Bash Here for D:\Softwares\Git
│   └── screenshots/                      ← 25 PNGs wired below (placeholders OK)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── data/.gitkeep                     ← db + notifications.log appear here at runtime
│   ├── scripts/seed_demo.py
│   ├── app/
│   │   ├── main.py                       ← routes, middleware, lifespan
│   │   ├── db.py                         ← schema create / migrate
│   │   ├── models.py                     ← pydantic request/response shapes
│   │   ├── rate_limit.py
│   │   ├── notifications.py              ← fake email/SMS append-only log
│   │   └── engine/
│   │       ├── dialogue.py               ← states + turn logic
│   │       ├── parser.py                 ← intents + slot extraction
│   │       └── availability.py           ← tables + SQLite bookings
│   └── tests/
│       ├── conftest.py
│       ├── test_parser.py
│       ├── test_dialogue.py
│       └── test_admin_api.py
└── frontend/
    ├── Dockerfile
    ├── nginx/default.conf                ← proxies /api → api service in Compose
    ├── package.json / package-lock.json
    ├── vite.config.js                    ← dev proxy /api → :8000
    ├── index.html
    └── src/
        ├── main.jsx / Shell.jsx          ← hash routing talk vs admin
        ├── App.jsx                       ← talk UI
        ├── Admin.jsx                     ← staff panel
        ├── api.js / speech.js
        └── App.css / index.css
```

**Do not submit** `.venv/`, `node_modules/`, `dist/`, `*.db`, `notifications.log`, `__pycache__/`, `.pytest_cache/`. `.gitignore` already excludes those.

---

## Prerequisites

| Tool | Why | Check |
| --- | --- | --- |
| Python 3.10+ | backend + pytest | `python --version` |
| Node.js 18+ and npm | frontend | `node -v` / `npm -v` |
| Git | clone / branch / PR later | `git --version` |
| Chrome or Edge | mic recognition | — |
| Docker Desktop (optional) | `run-docker.bat` | `docker version` |

On this PC Git lives at **`D:\Softwares\Git`**. See the next section (and `docs/GIT_BASH_WINDOWS_SETUP.md`) so Git Bash works from search and from right-click.

---

## Git on this Windows machine (`D:\Softwares\Git`)

### Add to User PATH

Add both:

```text
D:\Softwares\Git\cmd
D:\Softwares\Git\bin
```

PowerShell one-liner (User PATH):

```powershell
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path", "User") + ";D:\Softwares\Git\cmd;D:\Softwares\Git\bin",
  "User"
)
```

Open a **new** terminal afterward.

### Git Bash Here + Start search

- Re-run the Git installer → enable **Windows Explorer integration** → **Git Bash Here**.
- Win11: right-click → **Show more options** → Git Bash Here.
- Start menu: search **Git Bash**.

Verify:

```bash
git --version
bash --version
```

Full write-up: [`docs/GIT_BASH_WINDOWS_SETUP.md`](docs/GIT_BASH_WINDOWS_SETUP.md).

---

## Setup on Windows (step by step)

Assume the clean folder is on the Desktop:

```text
C:\Users\CodeTech\Desktop\savvpro-test-voice-agent-SUBMIT
```

### Option A — double-click (easiest)

1. Open that folder in Explorer.
2. Double-click **`RUN_APP.bat`**.
3. First run installs pip packages + `npm install` (can take a few minutes).
4. Two console windows stay open (API + UI). Browser opens http://localhost:5173.
5. Leave those windows open while you demo.

### Option B — Git Bash / PowerShell by hand

```bash
cd /c/Users/CodeTech/Desktop/savvpro-test-voice-agent-SUBMIT

# Backend
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Git Bash on Windows
# PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Frontend (new terminal)
cd /c/Users/CodeTech/Desktop/savvpro-test-voice-agent-SUBMIT/frontend
npm install
```

Optional: copy `.env.example` to `.env` and change `ADMIN_PASSWORD` if you want. Default demo password stays **`admin`** and is shown on the Admin screen.

---

## Batch files — what each one does

| File | What it does |
| --- | --- |
| `RUN_APP.bat` | Creates venv if missing, `pip install`, starts `uvicorn` on **8000**, `npm install` if needed, `npm run dev` on **5173**, opens the browser. |
| `run.bat` | Calls `RUN_APP.bat` (same thing, shorter name). |
| `test.bat` | Activates venv (or creates it), runs `pytest -v` in `backend/`. |
| `run-docker.bat` | `docker compose up --build` (needs Docker Desktop running). |

Flags / ports worth knowing:

- API: `--port 8000` (uvicorn).
- UI: Vite default **5173**; Compose maps UI to host **8080**.
- Keep consoles open; closing them kills the servers.

---

## Run without batch files

Terminal 1:

```bash
cd backend
source .venv/Scripts/activate   # or .venv/bin/activate on Linux/macOS
uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173  
Admin: http://localhost:5173/#/admin  

Health JSON: http://localhost:8000/api/health  

---

## Docker Compose

```bash
docker compose up --build
# or double-click run-docker.bat
```

| Service | Host URL |
| --- | --- |
| UI (nginx) | http://localhost:8080 |
| API | http://localhost:8000 |
| Admin | http://localhost:8080/#/admin |

SQLite file is volume-mounted so bookings survive container restarts (same idea as local `backend/data/`).

---

## How the dialogue brain works (short)

States (happy path):

`greeting` → `ask_date` → `ask_time` → `ask_party` → `confirm` → `booked` → `goodbye`

Also: `cancelled` if the caller bails; stay-in-state on unclear; jump back if they change a slot mid-flow.

One turn:

1. Parse raw text → intent + optional slots (`parser.py`).
2. Merge slots (supports “make it 8 instead” while already collecting).
3. Reject times outside dinner hours.
4. When date+time+party exist → check fake tables vs active SQLite rows.
5. If full → clear time, offer up to 3 nearby opens.
6. On confirm yes → INSERT booking, write fake notification, return ticket + `DecisionTrace`.

**No LLM chooses the next question.** The UI’s right-hand panel is there so a reviewer can see that.

Bare hours like `at 7` are biased to **PM** for this restaurant (dinner). `11 pm` is still rejected as outside service.

More detail: [`DESIGN.md`](DESIGN.md).

---

## How to demo a booking

1. Start the app (`RUN_APP.bat`).
2. Wait for the greeting; API pill should be green.
3. Type: `Friday at 7 for 4` → Enter / Send.
4. Read the summary → type `yes`.
5. Note the **booking id** on the ticket.
6. Open **Admin (pass: admin)** → unlock with `admin` → see the row.
7. Optional: Seed demo, Export CSV, Cancel, Restore.
8. Optional: open `backend/data/notifications.log` in a text editor — one fake “email/SMS” line per book.

Mic path (Chrome/Edge): click **Mic**, allow permission, speak clearly, wait for the transcript, same flow.

---

## Messy caller cases worth trying

| You say / type | Expect |
| --- | --- |
| `Friday at 7 for 4` then `yes` | Happy path ticket |
| After a time is set: `make it 8` / `8 instead` | Time updates; flow continues |
| Fill a slot that is already taken (seed + book same slot) | Alternatives offered |
| `cancel` mid-flow | Ends in cancelled |
| `what's the weather` | Polite redirect to booking |
| `asdfasdf` | Stays in state; asks again with an example |
| `11 pm` | Rejected; dinner hours reminder |
| Click **Reset** | New session / greeting |

---

## Admin panel (password on screen)

- URL: http://localhost:5173/#/admin  
- Talk UI button label includes **`Admin (pass: admin)`**.
- Unlock page shows a green banner: **Demo password: `admin`**.
- Header: `X-Admin-Password` (see `frontend/src/api.js`).
- Features: stats, search, seed demo rows, CSV export, soft cancel, restore, open-slots helper.

Change the password via `ADMIN_PASSWORD` in `.env` if you want — then update what you tell demo watchers (the UI default hint still says `admin` unless you change the frontend constant too).

---

## API endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/turn` | — (rate limited) | One dialogue turn; returns reply, decision, optional booking + confirmation |
| `POST` | `/api/reset` | — | Clear session state |
| `GET` | `/api/health` | — | `db_ok`, booking counts, latency-friendly ping |
| `GET` | `/api/admin/bookings` | `X-Admin-Password` | List; query `date`, `q` |
| `DELETE` | `/api/admin/bookings/{id}` | admin | Soft cancel |
| `POST` | `/api/admin/bookings/{id}/restore` | admin | Restore if table free |
| `GET` | `/api/admin/stats` | admin | Counts |
| `GET` | `/api/admin/bookings.csv` | admin | CSV download |
| `POST` | `/api/admin/seed` | admin | Insert demo rows |
| `GET` | `/api/admin/open-slots` | admin | Query `date`, `party_size` |

Responses include request id headers for log correlation.

---

## Tests

```bash
# Windows
test.bat

# or
cd backend
source .venv/Scripts/activate
pytest -v
```

About **25** tests. Under pytest the suite uses a **temp SQLite file** and turns rate limiting off unless a test enables it on purpose.

Coverage includes: parser edge cases, happy path, mid-flow time change, full slot + alternatives, cancel, deny-at-confirm, health, admin auth failure, CSV, seed, cancel/restore, persistence across engine instances, rate limit when enabled.

---

## Design / AI usage docs

- [`DESIGN.md`](DESIGN.md) — states, architecture sketch, messy-caller table, what is still cloud-only.
- [`AI_USAGE.md`](AI_USAGE.md) — honest note on assistant help vs hand-written brain; no runtime LLM.
- [`TASK.md`](TASK.md) — assessment brief kept in-tree for convenience.
- [`docs/GIT_BASH_WINDOWS_SETUP.md`](docs/GIT_BASH_WINDOWS_SETUP.md) — Windows Git path / Bash Here.

---

## Screenshots (01–25)

These PNGs live in `docs/screenshots/`. They are **labeled placeholders** you can replace with real captures from your machine before a live review. Alt text marks them as placeholders.

### 01 — App home

![placeholder — replace with your capture: App home](docs/screenshots/01-app-home.png)

Talk view after load: greeting, mic/send, decision panel empty or first turn.

### 02 — Mic permissions

![placeholder — replace with your capture: Mic permissions](docs/screenshots/02-mic-permissions.png)

Browser asking for microphone access (Chrome/Edge).

### 03 — Typed booking start

![placeholder — replace with your capture: Typed booking start](docs/screenshots/03-typed-booking-start.png)

Caller typed something like `Friday at 7 for 4`.

### 04 — Slot fill

![placeholder — replace with your capture: Slot fill](docs/screenshots/04-slot-fill.png)

Date / time / party reflected in the decision / slot UI.

### 05 — Confirm

![placeholder — replace with your capture: Confirm](docs/screenshots/05-confirm.png)

Assistant restates the booking and waits for yes/no.

### 06 — Confirmation ticket

![placeholder — replace with your capture: Ticket](docs/screenshots/06-ticket.png)

Booking id + printable-style ticket after confirm.

### 07 — Decision trace

![placeholder — replace with your capture: Decision trace](docs/screenshots/07-decision-trace.png)

State before/after, intent, action, notes.

### 08 — Change time mid-flow

![placeholder — replace with your capture: Change time mid-flow](docs/screenshots/08-change-time-midflow.png)

`make it 8` / `8 instead` updates the time slot.

### 09 — Full slot + alternatives

![placeholder — replace with your capture: Full slot alternatives](docs/screenshots/09-full-slot-alts.png)

Requested time full; nearby opens offered.

### 10 — Cancel flow

![placeholder — replace with your capture: Cancel flow](docs/screenshots/10-cancel-flow.png)

Caller cancels; session ends cleanly.

### 11 — Admin unlock + password banner

![placeholder — replace with your capture: Admin unlock + password](docs/screenshots/11-admin-unlock.png)

Green banner shows **Demo password: admin**.

### 12 — Admin stats

![placeholder — replace with your capture: Admin stats](docs/screenshots/12-admin-stats.png)

Active / cancelled (and related) counts.

### 13 — Seed demo

![placeholder — replace with your capture: Seed demo](docs/screenshots/13-seed-demo.png)

Seed button inserts demo bookings for the table.

### 14 — Bookings table

![placeholder — replace with your capture: Bookings table](docs/screenshots/14-bookings-table.png)

List with search / filters.

### 15 — Cancel booking (admin)

![placeholder — replace with your capture: Cancel booking](docs/screenshots/15-cancel-booking.png)

Soft cancel from admin.

### 16 — Restore

![placeholder — replace with your capture: Restore](docs/screenshots/16-restore.png)

Cancelled row restored when the table is free.

### 17 — Open slots

![placeholder — replace with your capture: Open slots](docs/screenshots/17-open-slots.png)

Availability helper for a date / party size.

### 18 — CSV export

![placeholder — replace with your capture: CSV export](docs/screenshots/18-csv-export.png)

Download `bookings.csv`.

### 19 — API health JSON

![placeholder — replace with your capture: API health JSON](docs/screenshots/19-api-health-json.png)

Browser or curl on `GET /api/health`.

### 20 — Pytest green

![placeholder — replace with your capture: Pytest green](docs/screenshots/20-pytest-green.png)

`pytest -v` / `test.bat` all passing.

### 21 — Docker compose up

![placeholder — replace with your capture: Docker compose up](docs/screenshots/21-docker-compose-up.png)

Compose running; UI on :8080.

### 22 — notifications.log

![placeholder — replace with your capture: notifications.log](docs/screenshots/22-notifications-log.png)

Fake email/SMS lines after a book.

### 23 — Project tree

![placeholder — replace with your capture: Project tree](docs/screenshots/23-project-tree.png)

Explorer / tree of `backend`, `frontend`, `docs`.

### 24 — Reset call

![placeholder — replace with your capture: Reset call](docs/screenshots/24-reset-call.png)

Reset clears the session; new greeting.

### 25 — Offline API banner

![placeholder — replace with your capture: Offline API banner](docs/screenshots/25-offline-api-banner.png)

UI warning when health check fails (API stopped).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Port 8000 in use | Old uvicorn still running | Close the old console, or `netstat -ano \| findstr :8000` and end that PID |
| Port 5173 in use | Old Vite | Same idea for 5173 |
| Mic does nothing | Firefox / denied permission / no HTTPS quirks | Use **Chrome or Edge**; allow mic; typed input still works |
| API pill red | Backend not up | Start `RUN_APP.bat` or uvicorn; open `/api/health` |
| `git` not recognized | PATH missing `D:\Softwares\Git\cmd` | See Git section above; new terminal |
| Nested `savvpro-test-voice-agent\savvpro-test-voice-agent\` confusion | Old unzip layout | Submit folder is **flat**: `Desktop\savvpro-test-voice-agent-SUBMIT\` with `backend` and `frontend` directly inside |
| Admin 401 | Wrong password | Default is `admin` (shown on screen) |
| Empty bookings after restart | Looking at a different cwd / db path | Confirm `backend/data/bookings.db` next to the running API |
| Docker UI 8080 but API calls fail | Compose not up / proxy | `docker compose ps`; check `frontend/nginx/default.conf` |
| pytest import errors | Wrong directory / no venv | Run from `backend` with venv active |

---

## Submission checklist (you do GitHub)

Do this yourself when ready — do **not** expect the build machine to push.

1. In the browser: fork `https://github.com/savvpro/savvpro-test-voice-agent`.
2. Clone **your** fork (not the upstream only).
3. Copy the contents of `savvpro-test-voice-agent-SUBMIT` into that clone (or init git inside SUBMIT and add your fork as `origin`).
4. `git checkout -b candidate-<your-github-username>`
5. Commit source only (no `node_modules`, `.venv`, db files).
6. `git push -u origin candidate-<your-github-username>`
7. Open a Pull Request **into** `savvpro/savvpro-test-voice-agent` **`main`**.
8. Double-check README screenshots / AI_USAGE before you click Create.

Exact copy-paste commands are in the chat message that accompanies this folder (ask me again if you lost them).

**GitHub Actions:** not included on purpose. The assessment org may not enable Actions. If you want CI, add it only on a fork you own — do not assume you can turn Actions on for `savvpro/*`.

---

## Local “pro” vs cloud (honest)

### Done in this free local tree

- Deterministic non-LLM brain + decision trace UI  
- SQLite persistence, soft cancel/restore  
- Lifespan startup, request ids, latency logs  
- In-memory rate limit on `/api/turn`  
- Health with DB status  
- Confirmation ticket + fake notification log  
- Admin: password-on-screen demo, stats, seed, CSV, open slots  
- CORS allow-list for local origins  
- Docker Compose path  
- Windows batch launchers  
- Expanded pytest suite  
- Long README + screenshot slots + Git Bash setup doc  

### Needs cloud / paid / multi-node (out of free local scope)

- Real phone numbers (Twilio / Vonage)  
- Real SMS / email delivery  
- Streaming cloud STT or GPU Whisper  
- Postgres + managed backups  
- Redis shared rate limit across many API replicas  
- Real staff login (OIDC), not one shared password  
- Public HTTPS, CDN, Sentry  
- Org-level GitHub Actions on `savvpro/*` (use your own fork if you want CI)

---

## Env knobs

See `.env.example`. Common ones:

| Variable | Meaning | Default idea |
| --- | --- | --- |
| `ADMIN_PASSWORD` | Admin header password | `admin` |
| `BOOKINGS_DB` | SQLite path override | `backend/data/bookings.db` |
| `CORS_ORIGINS` | Allowed browser origins | localhost Vite / Compose |
| Rate-limit related | Window / max turns | set in code / env as documented in `.env.example` |

Never commit a real production secret. This take-home is demo-grade auth on purpose.

---

## License / ownership note

Assessment work for SAVV Pro Solutions take-home. Restaurant name and copy are fictional. Follow the assessment’s submission rules on the original GitHub README if anything here disagrees — upstream instructions win for deadline / PR target.
