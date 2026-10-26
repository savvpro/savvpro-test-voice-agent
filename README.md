# Smile Dental — voice appointment assistant

A phone-style voice assistant for a (fictional) dental clinic. A caller speaks, the browser turns speech into text,
a **Python brain made of plain rules** (no GPT / Claude / Gemini / any LLM) decides what to do and what to say, and the
browser reads the answer back.

```
caller ──► microphone ──► speech-to-text ──► BRAIN (rules, Python) ──► text-to-speech ──► speaker
                          (browser)           NLU → policy → templates    (browser)
```

* **Use case:** book a dental appointment (checkup, cleaning, filling, root canal, wisdom-tooth extraction).
  Cancel / reschedule requests are *detected* and answered with "please call the front desk".
* **Data:** everything is fake (clinic, prices, demo patients, phone numbers).
* **Design:** see [DESIGN.md](DESIGN.md) (use case, sample calls, how the brain decides).
  **AI help:** see [AI_USAGE.md](AI_USAGE.md).

## How a turn works

1. The browser turns speech into text (Web Speech API) and sends it to `POST /api/sessions/{id}/turns`.
2. **NLU** finds the intents (what the caller wants) and the values (service, date, time, name, phone).
3. **Policy** looks at those, the call's memory (state + slots) and the calendar, and decides what to do.
4. **Responses** are fixed sentences with blanks; the policy picks one and fills it in.
5. The reply goes back; the browser shows it and reads it aloud.

## Repository layout

```
backend/                   Python 3.11+ (FastAPI)
  app/services/booking.py    clinic calendar: opening hours, 30-min grid, double-booking protection
  app/brain/nlu.py           intents + services (phrase lists), text normalising
  app/brain/extractors.py    time, date, phone, name, choice, relation
  app/brain/parser.py        runs every extractor on one sentence -> NLUResult
  app/brain/policy.py        THE DECISIONS (state machine + slot filling)
  app/brain/responses.py     every sentence the assistant can say (fixed templates)
  app/brain/assistant.py     one call = NLU + policy glued together
  app/api/                   HTTP endpoints, session store
  app/cli.py                 talk to the brain in the terminal
  tests/                     pytest: unit tests, whole-call scenario tests, API tests
frontend/                  Next.js 14 (TypeScript): microphone, speaker, transcript, "brain panel"
```

## Run it

You need Python 3.11+ and Node 18+. Chrome or Edge give you the microphone; other browsers can type instead.

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # optional, the defaults work
uvicorn app.main:app --reload --port 8000
```

Try the brain in the terminal without any browser: `python -m app.cli`

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local        # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                       # http://localhost:3000
```

Press **Start call**, allow the microphone, and talk — or type in the box. The right-hand panel shows the state,
the filled slots, the detected intents and *why* each decision was made.

### Try these sentences

* "I need a cleaning tomorrow at 2 pm" → then a name, a phone number, then "yes"
* "Wisdom tooth extraction tomorrow at 9 am" → 9:00 is taken in the demo calendar, so it offers other times → "the second one"
* "How much is a root canal?" … "Can you make it 8k?" → polite refusal, the pending question is asked again
* "Yes, but make it 1 pm" at the confirmation → the time changes and it asks to confirm again
* "I'm in severe pain" → earliest free slots
* Say nonsense three times → it hands the caller to the front desk

## Troubleshooting

| Problem | Fix |
|---|---|
| `python -m pytest` says `No module named 'app'` | Run it from the `backend/` folder |
| The page says "Could not reach the assistant" | Start the backend (port 8000) and check `NEXT_PUBLIC_API_URL` in `frontend/.env.local`; restart `npm run dev` after changing it |
| Browser blocks the request (CORS) | Set `ALLOWED_ORIGINS` in `backend/.env` to the exact address of the frontend |
| The mic button is disabled | Use Chrome or Edge, allow the microphone, and open the site on `localhost` (or HTTPS). Typing always works |
| Port already in use | Pick another one: `uvicorn app.main:app --port 8001`, then update `NEXT_PUBLIC_API_URL` |

## Tests

```bash
cd backend && python -m pytest -v                     # brain, calendar, whole-call scenarios, API
cd frontend && npm test && npm run typecheck && npm run build
```

The clock is injected (`Assistant(calendar, clock=...)`), so tests never depend on today's date.

## Configuration

| Variable | Where | Meaning | Default |
|---|---|---|---|
| `ALLOWED_ORIGINS` | backend | CORS origins, comma separated | `http://localhost:3000` |
| `SEED_DEMO_DATA` | backend | pre-book a few fake slots tomorrow | `true` |
| `NEXT_PUBLIC_API_URL` | frontend | where the API lives | `http://localhost:8000` |

No keys, passwords or tokens are needed or committed. The clinic's clock is the server's local time.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness |
| POST | `/api/sessions` | start a call; returns `session_id` and the greeting |
| POST | `/api/sessions/{id}/turns` | body `{"text": "..."}`; returns reply, state, slots, intents, actions, trace |
| GET | `/api/sessions/{id}` | current state and slots |

## Known limits

* Sessions and the calendar live in memory: restarting the server forgets them.
* English only; accuracy on accents and noise depends on the browser's speech recognition.
* Cancel and reschedule are detected but not performed.
* A real phone line would need a telephony provider in front of the same brain; the brain only needs text in and text out.