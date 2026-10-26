# Bright Smile Dental – Voice Assistant

A voice assistant that does a real phone job from start to end: **booking, moving and cancelling
dental appointments**. The caller talks, the browser turns speech into text, a Python "brain"
decides what to do, and the browser reads the reply out loud.

```
Caller speaks -> Speech to text (browser) -> Brain (Python rules) -> Text to speech (browser) -> Caller hears
```

The brain is plain code (regexes, lookup tables, a state machine). **No GPT, Claude, Gemini or any
other AI model makes decisions.** See [DESIGN.md](DESIGN.md) for how it works.

## Requirements

- Python 3.10+
- Node.js 18+
- Chrome or Edge for voice input (Web Speech API). Other browsers can still use the text box.
- No API keys or accounts are needed. All data is fake.

## Get the project

Fork `savvpro/savvpro-test-voice-agent` on GitHub, then clone your fork:

```bash
git clone https://github.com/<your-github-username>/savvpro-test-voice-agent.git
cd savvpro-test-voice-agent
git switch -c candidate-<your-github-username>
```

Replace `<your-github-username>` with your GitHub username. Run these commands from the repository root. The examples below use PowerShell.

## Run it

Backend (terminal 1, PowerShell):

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

If PowerShell blocks virtual environment activation, you can run the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontend (terminal 2, from the repository root):

```powershell
cd frontend
npm install
npm run dev
```

On Windows, `npm` commands run in PowerShell as written. Open http://localhost:5173, press
**Start call**, allow the microphone, and talk.
The right-hand panel shows what the assistant understood and which rule it used.

## Submit your assessment

Commit and push your work to your candidate branch:

```bash
git add .
git commit -m "feat: complete voice-agent assessment"
git push -u origin candidate-<your-github-username>
```

Then open a pull request from your fork's candidate branch to
`savvpro/savvpro-test-voice-agent:main`. Follow the assessment instructions for the PR title and
base/head repositories. Complete only this assessment; do not submit Test 1 as well.

## Try these

- "I'd like a cleaning next Tuesday afternoon" (then answer its questions)
- "Cancel my appointment" -> name: "Sara Khan" (one fake demo appointment is created at startup)
- Change your mind: say "actually make it 4 PM" when it asks you to confirm
- Ask for a Sunday, a time in the past, or 3:30 PM and see how it reacts

## Tests

```powershell
cd backend
python -m pytest                      # NLU, dialogue flows, API
cd ..\frontend
npm test                              # API client
npm run build                         # production frontend build
```

Run the Python and frontend commands in separate terminals if you want to keep the backend server
running while testing the frontend.

## Project layout

```
backend/app/nlu.py        understands text: dates, times, services, names, intents
backend/app/scheduler.py  fake appointment book and opening hours
backend/app/brain.py      the dialogue manager (state machine) and its reasoning trace
backend/app/main.py       FastAPI endpoints
backend/tests/            pytest tests
frontend/src/             React app (call screen, speech hook, API client)
```

## API

| Method | Path | What it does |
|---|---|---|
| POST | `/api/sessions` | Start a call, returns the greeting |
| POST | `/api/sessions/{id}/turn` | Send `{ "text": "..." }`, get the reply, state, slots and trace |
| GET | `/api/health` | Health check |

## Known limits

Sessions and appointments live in memory (they reset when the server restarts). Voice input uses
the browser's Web Speech API, which needs an internet connection in Chrome.
