# Mezban — restaurant voice concierge

A fictional Lahore restaurant receptionist for à la carte, hi-tea and dinner buffet reservations. Python rules make every decision. React displays the conversation, booking details and the exact rule applied. No LLM is called at runtime.

## Setup

Prerequisites: Python 3.12+, Node 22+, and Chrome or Edge for browser speech. No API keys required. Use fake names and numbers only.

From the repository root (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

If Python is available through uv instead, use `uv venv .venv` and `uv pip install --python .venv\Scripts\python.exe -r backend\requirements-dev.txt`.

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. API docs: http://127.0.0.1:8011/docs.

On macOS/Linux, use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r backend/requirements.txt`, then run `../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8011` from `backend`.

The Vite proxy targets port 8011. SQLite is created automatically at `backend/mezban.db`. Set `MEZBAN_DB` to override its location.

## Try it

Tap the microphone for each turn, or type:

1. `hi-tea tomorrow at 6 PM`
2. `2 adults`
3. `children aged 3 and 7`
4. `indoor`
5. `name is Demo Guest`
6. `03000000000`
7. `yes`
8. Click **Simulate deposit**.

Total: PKR 5,000; simulated deposit: PKR 1,250. No money moves. À la carte bookings confirm immediately after the final yes.

Try `price?` halfway through, change to `4 PM`, switch with `normal menu`, or say `cancel` followed by `yes`. Use **Manage an existing booking** with a reference and its fictional phone number to resume after a new call or page refresh.

## Fictional policies

- Lahore timezone: Asia/Karachi.
- À la carte arrivals: daily noon–9 PM, two-hour table duration; order food on arrival.
- Hi-tea: daily 4 PM and 6 PM, 90 minutes, PKR 2,000/adult.
- Dinner buffet: Friday–Sunday at 8 PM, two hours, PKR 3,000/adult.
- Under 4 free; ages 4–9 half price; 10+ adult rate. All children occupy capacity.
- Buffet prices include demo tax, water and tea; soft drinks extra.
- Indoor and rooftop each have three joinable four-seat tables shared across dining modes.
- Maximum party 12. Larger parties, allergies, accessibility, decorations and seasonal packages need staff. Assistance requests are stored locally; no staff is contacted.
- Buffet holds expire after ten minutes. Simulated deposit: 25%. No real payments/refunds.
- Fifteen-minute arrival grace is disclosed; operational arrival and no-show tracking are outside this version.

## Checks

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ../frontend
npm run build
npm run test:e2e
```

Browser tests require installed Google Chrome locally. They start their own servers on ports 5174/8012 and use a fresh temporary database, then clean up automatically. They do not use your manual-test database. CI installs Playwright Chromium and runs the same flows. Override `MEZBAN_PYTHON` if your Python interpreter is not at the default virtual-environment path.

For a complete Windows preflight, run `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`. This also scans source/evidence for common secret patterns and checks Python/frontend formatting. Then follow [the final acceptance checklist](docs/FINAL_TEST.md) for physical microphone/speaker testing. Repeated manual bookings can fill the demo database; choose another date or start with a fresh database.

## Speech and limitations

Browser SpeechRecognition transcribes; browser SpeechSynthesis speaks English Python response templates. Select English or Urdu recognition independently; replies remain English. Use **Replay assistant reply** to check speaker output. The browser vendor may process audio remotely. Microphone permission is required; support, Urdu accuracy, network needs and voices vary by browser/OS. Typing exercises the identical backend. English and limited Roman Urdu are supported; unrestricted Urdu understanding is not promised. Fonts are bundled locally, so the interface does not depend on external font services.

This first implementation uses browser speech, native CSS and Python's SQLite driver instead of the previously proposed Whisper/Azure, Tailwind and SQLAlchemy stack. It runs without credentials or model downloads. The brain is independent of its transport.

This is a local assessment demo. Session IDs are bearer capabilities; reference-plus-phone lookup is demo verification, not production authentication. Public deployment requires authentication, rate limits, retention controls, migrations and real payment reconciliation.

## Structure

```text
backend/app/brain.py       Parsing, dialogue state and restaurant rules
backend/app/store.py       Transactional SQLite and capacity checks
backend/app/main.py        FastAPI endpoints and orchestration
backend/tests/             Unit and integration tests
frontend/src/              React voice UI and decision inspector
frontend/e2e/              Real-browser workflow tests
.github/workflows/ci.yml   Backend tests and frontend build
DESIGN.md                  Decision design and tradeoffs
AI_USAGE.md                AI assistance record and usage limitations
TASK.md                    Original assessment
```
