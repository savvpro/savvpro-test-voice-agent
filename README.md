# Penny — personal expense logging voice assistant

A small full-stack voice assistant for logging personal expenses. Say or type something like “I spent $12.50 on lunch yesterday”; the assistant extracts the amount, category, and date, reads the entry back, and saves it after confirmation. The browser provides speech recognition and spoken replies when supported. The Python backend owns all intent handling and decisions using deterministic rules; no language model is used at runtime.

**Stack:** Python / FastAPI backend + React frontend. Node.js is only used by npm and Vite to install, develop, and build the React frontend; there is no Node.js backend.

## Requirements

- Python 3.10 or newer
- Node.js 20 or newer and npm (frontend development/build tools only)
- A modern browser. Microphone speech recognition is supported in Chromium-based browsers; typed chat works in all modern browsers.

## Run locally
Follow these exact, copy-pasteable commands from the repository root. These are for Windows PowerShell (adjust `python` / `pip` to your system if needed).

Open two PowerShell terminals (or tabs). In the FIRST terminal run the backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

When the backend starts the API will be available at http://localhost:8000 and the interactive docs at http://localhost:8000/docs

In the SECOND terminal start the frontend dev server:

```powershell
cd frontend
npm install
npm run dev
```

Vite will print a local URL (usually http://localhost:5173). Open that page in a Chromium-based browser for speech recognition, or any modern browser for typing input. The frontend expects the backend at `http://localhost:8000` by default; to point it to a different backend set `VITE_API_URL` before running Vite, for example:

```powershell
#$env:VITE_API_URL = 'http://127.0.0.1:8000'
npm run dev
```

### Run tests and rebuild

Run backend tests from the backend folder:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

Build the production frontend bundle:

```powershell
cd frontend
npm run build
```

## Tests and production build

```powershell
cd backend
python -m pytest -q
```

```powershell
cd frontend
npm run build
```

## Intent improvement loop

Intent examples, slots, and reply templates live in [backend/config/intents.json](backend/config/intents.json). Rebuild the small explainable classifier with one command:

```powershell
cd backend
python train.py
```

The command reads the JSON examples plus reviewer labels from `backend/data/corrections.jsonl`, evaluates held-out examples, writes `backend/data/intent_model.json` and `backend/data/eval_report.json`, and prints held-out accuracy, confidence quality, per-intent metrics, and a confusion matrix. The model normalizes amount tokens, common synonyms, typos, and unigram/bigram features. The regression suite checks that classifier accuracy does not fall below the safety threshold:

```powershell
python -m pytest -q
```

Every API turn is appended to `backend/data/turns.jsonl` with a turn ID, predicted intent, confidence, flags, and decision trace. Low-confidence, fallback, and negative-feedback turns are marked for review. Each assistant response has a `Wrong intent?` control; selecting the correct label writes to `corrections.jsonl`, which the next `python train.py` run includes.

Latest trained model (local): see `backend/data/eval_report.json` for the most recent held-out evaluation. Current build (after adding more held-out examples) reports:

- Held-out samples: 33
- Accuracy: 0.848 (84.8%)
- Mean confidence when correct: 0.885
- Mean confidence when wrong: 0.24
- Confident share (>= 0.75): 0.706
- Accuracy when confident: 1.00
- Brier score: 0.0639

These metrics are printed by `python train.py` and the full report is written to `backend/data/eval_report.json`.

## Conversation behavior and privacy

The assistant collects an amount and category, uses today as the date if none is given, repeats the entry for confirmation, and adds confirmed expenses to a running total. It supports multiple expenses in one sentence, relative dates such as `yesterday`, `last Friday`, and `two days ago`, spoken amounts such as `four fifty`, `twelve hundred`, `5k`, and `fifty bucks`, explicit USD/EUR/GBP or the configured default currency, corrections, and discarding a draft. It asks for missing amounts instead of guessing, asks for clarification on vague store purchases, and rejects income or unrelated questions. Dates are resolved by the Python backend using its current date; there is no runtime LLM and therefore no date prompt to pass to one. Confirmed expense records are stored in the local SQLite database at `backend/data/expenses.db`, keyed by the browser's session ID, and are restored after a backend restart or page reload. They are not sent to a third-party service. The reset button clears the current session from SQLite. This is a demo, not a secure personal-finance product.

See [DESIGN.md](DESIGN.md) for the decision flow and limitations and [AI_USAGE.md](AI_USAGE.md) for AI-tool usage disclosure.

## Frontend features (recent updates)

- Dark theme tuned to a black background with a green accent (accent color: #23dc70).
- Sticky top navbar with brand mark and compact controls.
- Voice input via Web Speech API and speech synthesis replies; an audio toggle lets users play/stop the assistant reply at any time.
- CSV export: download session expenses as CSV from the UI (Download CSV button).
- Per-currency category charts: open the "View chart" modal to see a per-currency pie breakdown for the current month and select the currency to view totals for that currency. The center label shows the total for the selected currency (other currencies are listed too).
- Responsive layout: wider, taller chat panel on desktop; mobile layout and spacing fixed to preserve usability.
- Accessibility and UX polish: larger message font, clearer headings, and compact composer controls.
