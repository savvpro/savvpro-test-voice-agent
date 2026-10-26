# Voice Booking Assistant — The Copper Spoon

A voice agent that books restaurant tables over the phone. Built for the
SavvPro voice-agent assessment.

> **The one big rule:** the brain is 100% hand-written Python. No LLM, no
> embeddings, no model files. Just a finite state machine + regex slot
> extractors + keyword intent classification.

## What it does

A caller phones the restaurant. The assistant:

1. Greets them.
2. Asks for the **day**, **time**, and **party size** (in any order, all at once, or one at a time).
3. Checks table **availability** against a fake bookings store (with operating hours, table sizes, and existing bookings).
4. Asks for the **name** and **phone number**.
5. **Confirms** the reservation back to the caller.
6. On "yes", **books** the table and gives a confirmation number.
7. Says goodbye and ends the call.

It also handles messy-caller scenarios:

- **Mid-flow changes**: "actually change the time to 6:30" re-validates availability and re-confirms.
- **Side questions**: "wait, what are your hours?" is answered, then the brain returns to the booking.
- **Repeats**: "can you repeat that?" replays the last prompt.
- **Cancellations**: "cancel" wipes the in-progress booking.
- **Unavailable slots**: offers the closest available alternatives.
- **Closed days / outside hours**: explains the operating hours.
- **Gibberish / silence**: reprompts gracefully.

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                       Browser (caller)                     │
│                                                            │
│  ┌──────────────┐         ┌──────────────────────────┐    │
│  │ Web Speech   │  STT    │  Next.js frontend        │    │
│  │ Recognition  │ ──────> │  (React + Tailwind)      │    │
│  │ (mic input)  │         │                          │    │
│  └──────────────┘         │  - mic button            │    │
│                           │  - live transcript        │    │
│  ┌──────────────┐         │  - brain decision panel  │    │
│  │ Web Speech   │  TTS    │  - slot grid             │    │
│  │ Synthesis    │ <────── │                          │    │
│  │ (spoken reply│         └──────────┬───────────────┘    │
│  └──────────────┘                    │ POST /api/chat     │
└──────────────────────────────────────┼─────────────────────┘
                                       │ (text only)
                                       ▼
┌────────────────────────────────────────────────────────────┐
│              Python FastAPI backend (port 8000)            │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Brain (rule-based — NO LLM)                       │   │
│  │                                                    │   │
│  │  intents.py   keyword + regex intent classifier    │   │
│  │  slots.py     regex slot extractors                │   │
│  │  state_machine.py  finite state machine            │   │
│  │  restaurant.py     fake bookings + hours + tables  │   │
│  │  responses.py      response templates              │   │
│  │  sessions.py   in-memory session store             │   │
│  └────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

The brain runs entirely on the backend. STT and TTS run entirely in the
browser via the Web Speech API — no external API keys, no paid services.

## Project layout

```
.
├── backend/                    # Python FastAPI backend
│   ├── brain/
│   │   ├── __init__.py
│   │   ├── intents.py          # Keyword + regex intent classifier
│   │   ├── slots.py            # Regex slot extractors (date/time/party/name/phone)
│   │   ├── state_machine.py    # DialogueManager — the brain
│   │   ├── restaurant.py       # Fake operating hours, tables, booking store
│   │   └── responses.py        # Response templates
│   ├── tests/
│   │   ├── test_slots.py       # 30+ slot extractor tests
│   │   ├── test_intents.py     # 25+ intent classifier tests
│   │   ├── test_state_machine.py  # 20+ end-to-end brain tests
│   │   └── test_api.py         # 7 FastAPI endpoint tests
│   ├── main.py                 # FastAPI app
│   ├── sessions.py             # Session store
│   └── requirements.txt
├── src/                        # Next.js frontend
│   ├── app/
│   │   ├── page.tsx            # Main route — renders VoiceAssistant
│   │   └── layout.tsx
│   ├── components/
│   │   ├── voice-assistant.tsx # Main voice UI component
│   │   └── ui/                 # shadcn/ui components
│   └── lib/
│       ├── api.ts              # Backend API client
│       └── voice.ts            # Web Speech API wrappers (STT + TTS)
├── DESIGN.md                   # Brain design — read this!
├── AI_USAGE.md                 # AI tools used
├── pytest.ini
└── README.md                   # This file
```

## Prerequisites

- **Python 3.10+** with `pip`
- **Node.js 18+** and **bun** (or npm/pnpm)
- A browser that supports the **Web Speech API** for STT (Chrome, Edge, Safari). Firefox supports TTS but not STT — the text input fallback works everywhere.

## Setup & run

### 1. Backend

```bash
# from the repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# start the API server on port 8000
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify it's up:

```bash
curl http://localhost:8000/api/health
# {"ok": true, "version": "1.0.0", "bookings_count": 4, ...}
```

### 2. Frontend

```bash
# from the repo root
bun install         # or: npm install
bun run dev         # or: npm run dev
```

Open <http://localhost:3000>. Click the mic and say:

> "Hi, I'd like to book a table for tomorrow at 7pm for 4 people"

Or use the text input at the bottom of the page if your browser doesn't
support speech recognition.

### 3. Tests

```bash
# Brain unit tests + API tests
python3 -m pytest backend/tests/ -v
```

All 81 tests should pass.

## Sample conversation

```
Assistant:  Thanks for calling The Copper Spoon. I can help you book a table.
            What day would you like to come in?

Caller:     Hi, I want to book friday at 8pm for 4 people.

Assistant:  Last thing — what name should I put the reservation under?

Caller:     John Smith.

Assistant:  And a phone number where we can reach you?

Caller:     555-123-4567.

Assistant:  Let me confirm. A table for 4 on Friday, October 30 at 8 p.m.,
            under John Smith. Should I go ahead and book that?

Caller:     Yes.

Assistant:  You're all set. Your reservation is confirmed for 4 on Friday,
            October 30 at 8 p.m., under John Smith. Your confirmation number
            is B-2005. We'll see you then. Anything else?

Caller:     Bye.

Assistant:  Thank you for calling The Copper Spoon. Have a great day. Goodbye.
```

## Try saying

| Phrase | What happens |
|--------|--------------|
| "Hi, I'd like to book a table" | Starts a booking |
| "Tomorrow at 7pm for 4 people" | Fills 3 slots in one utterance |
| "Friday at 8 for 2" | Same — partial slot phrasing |
| "Actually change the time to 6:30" | Mid-flow change, re-validates availability |
| "What are your hours?" | Side question, answered, then returns to booking |
| "Can you repeat that?" | Repeats the last prompt |
| "Cancel" | Cancels the in-progress booking |
| "Bye" | Ends the call |

## What the brain decides — and how you can see it

The right-hand **Brain Decision** panel on the web page shows, for every turn:

- **Current state** — which state the state machine is in (e.g. `Asking: Time`, `Confirming`, `Booked`).
- **Intent detected** — what the classifier thought the caller wanted (e.g. `provide_party_size`, `change_value`, `ask_hours`).
- **Brain action** — the internal decision label (e.g. `need_name`, `availability_failed`, `side_ask_hours`, `booking_confirmed`).
- **Slots** — the current values of `date`, `time`, `party_size`, `name`, `phone`.
- **Booking ID** — once confirmed, the booking reference.

This makes the brain's behavior fully transparent — you can see exactly what
it decided and why at every turn.

## Tech choices & why

| Layer | Choice | Why |
|-------|--------|-----|
| Brain language | Python | Required by the task. Also great for regex + dataclasses. |
| Brain logic | Hand-written FSM + regex | Required by the task — no LLM allowed for decisions. |
| Backend framework | FastAPI | Async, automatic OpenAPI, Pydantic models, great DX. |
| STT / TTS | Browser Web Speech API | No API keys, no paid services, runs locally. The task explicitly allows any STT/TTS service. |
| Frontend | Next.js 16 + TypeScript + Tailwind + shadcn/ui | Required by the task (React/Next.js). shadcn/ui for fast, consistent components. |
| State | In-memory session store + in-memory booking store | Sufficient for a demo. Would swap for Redis + Postgres in production. |
| Tests | pytest + FastAPI TestClient | Fast, deterministic, covers slots/intents/state machine/API. |

## Production notes (what I'd add next)

- Replace the in-memory stores with Redis (sessions) and Postgres (bookings).
- Add authentication and per-restaurant tenancy.
- Stream audio to the backend and run STT there (Whisper) so we can support browsers without Web Speech API.
- Add a real TTS voice (ElevenLabs / OpenAI TTS) for less robotic delivery.
- Add metrics (turn success rate, fallback rate, booking completion rate).
- Internationalize the brain (multi-language intent + slot patterns).
- Add a confirmation step that sends an SMS / email with the booking details.

## License

MIT — this is a coding assessment, take whatever's useful.
