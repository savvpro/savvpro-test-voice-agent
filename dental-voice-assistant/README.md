# Dental Voice Assistant — BrightSmile Dental Clinic

A production-quality, rule-based voice assistant for a dental clinic. Callers speak (or type) to book, reschedule, and cancel appointments. No LLM is used — the brain is a fully deterministic state machine.

---

## Architecture

```
Caller → STT (Whisper/FakeSTT)
       → Brain (regex · rapidfuzz · dateparser · state machine)
       → TTS (EdgeTTS/FakeTTS)
       → Caller
```

| Layer     | Location       | Key tech                                        |
| :-------- | :------------- | :---------------------------------------------- |
| ai-tool   | `ai-tool/`     | Pure Python: ports, brain NLU, pipeline, STT/TTS |
| backend   | `backend/`     | FastAPI, SQLAlchemy 2 async, Alembic, WebSocket  |
| frontend  | `frontend/`    | React 18 + Vite + TypeScript                     |

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Docker (optional, for PostgreSQL)
- Node.js 18+ (for frontend)

### 2. Setup

```bash
# Install all Python dependencies
pip install -e ai-tool/
pip install -r backend/requirements.txt

# Or use the Makefile
make setup
```

### 3. Run the dev server

```bash
# Start backend (uses SQLite by default)
cd backend
uvicorn app.main:app --reload --port 8000

# Or with Docker Compose (includes PostgreSQL)
make dev
```

Set environment variables (copy `.env.example` → `.env`):

```bash
cp .env.example .env
```

Key variables:

| Variable                    | Default           | Purpose                            |
| :-------------------------- | :---------------- | :--------------------------------- |
| `STT_PROVIDER`              | `faster_whisper`  | `faster_whisper` or `fake`         |
| `TTS_PROVIDER`              | `edge_tts`        | `edge_tts`, `piper`, or `fake`     |
| `WHISPER_MODEL`             | `base.en`         | Model size (`tiny.en`, `base.en`)  |
| `WHISPER_DEVICE`            | `cpu`             | `cpu` or `cuda`                    |
| `MAX_CONCURRENT_CALLS`      | `10`              | Max simultaneous WS connections    |
| `DATABASE_URL`              | SQLite dev.db     | Full async SQLAlchemy URL          |

---

## WebSocket Protocol (`/ws/calls`)

All JSON frames sent by the server:

```json
// Turn (from server)
{
  "type": "turn",
  "turn": 1,
  "user_text": "I want a cleaning",
  "reply_text": "What day would you like to come in?",
  "state": "COLLECT_DATE",
  "end_call": false,
  "audio": "<base64-encoded MP3>",
  "audio_mime": "audio/mpeg",
  "timings": { "stt_ms": 210, "brain_ms": 1, "tts_ms": 320, "total_ms": 531 }
}

// Error (from server)
{ "type": "error", "error": "oversize_audio", "detail": "..." }

// Call ended (from server)
{ "type": "call_ended", "reason": "completed" }
```

Client sends:

```json
// Text input
{ "type": "user_text", "text": "book a checkup tomorrow at 10 AM" }

// Hang up
{ "type": "end" }

// Audio input: send raw bytes (WAV/WebM/MP3) as a binary WebSocket frame
```

---

## Manual Smoke Test — `scripts/ws_smoke_test.py`

This script connects to the live backend WebSocket, optionally sends a WAV audio file, then drives a complete booking dialog via text and prints all transcripts, replies, and timings.

### Install the one extra dependency

```bash
pip install websockets
```

### Run without audio (text-only dialog)

```bash
# Start the server first
cd backend
uvicorn app.main:app --reload --port 8000

# In another terminal
python scripts/ws_smoke_test.py
```

**Expected output:**

```
Connecting to ws://localhost:8000/ws/calls …

[TURN 0] 🤖 Hello, thank you for calling BrightSmile Dental Clinic. How can I help you today?
         (audio: 14832 bytes, audio/mpeg)
         timings: {'stt_ms': 0.0, 'brain_ms': 0.0, 'tts_ms': 312.4, 'total_ms': 312.4}

[SEND TEXT] "I'd like to book a checkup"
[TURN 1] 🤖 What day would you like to come in?
           ⏱  314ms total (stt=0ms brain=0ms tts=314ms)

[SEND TEXT] "Tomorrow"
[TURN 2] 🤖 What time works best for you? We are open Monday to Saturday from 9 AM to 5 PM.
           ⏱  290ms total (stt=0ms brain=0ms tts=290ms)

[SEND TEXT] "10 AM"
[TURN 3] 🤖 May I please have your full name?
           ...

✅ Booking complete! Waiting for call_ended frame …
[CALL ENDED] reason=completed
```

### Run with a WAV audio file

```bash
python scripts/ws_smoke_test.py --wav path/to/your/sample.wav
```

The WAV bytes are sent as a binary WebSocket frame. The server's STT engine (Whisper or FakeSTT) transcribes it and processes it through the dialog pipeline.

### Custom server URL

```bash
python scripts/ws_smoke_test.py --url ws://192.168.1.100:8000
```

---

## Testing

```bash
# All ai-tool tests (44 tests: 32 scenarios + 5 branch + 6 pipeline + 1 no-llm)
python -m pytest ai-tool/tests/ --cov=voice_agent.brain --cov-report=term-missing

# All backend tests (56 tests including 7 WebSocket tests)
python -m pytest backend/tests/

# Full suite
python -m pytest ai-tool/tests/ backend/tests/ -q

# Linting
python -m ruff check ai-tool backend
python -m ruff format --check ai-tool backend

# Type checking (strict mypy on ai-tool)
python -m mypy --config-file ai-tool/pyproject.toml ai-tool/src ai-tool/tests
```

---

## Project Structure

```
dental-voice-assistant/
│
├── ai-tool/                      # Pure Python voice agent
│   └── src/voice_agent/
│       ├── ports.py              # Protocols: STTEngine, TTSEngine, BookingGateway, Clock, TurnResult
│       ├── pipeline.py           # VoicePipeline (STT → Brain → TTS)
│       ├── brain/
│       │   ├── dialog.py         # FSM coordinator, fail_count, turn cap
│       │   ├── responses.py      # ← ALL reply strings live here
│       │   ├── state.py          # State enum + SessionContext
│       │   ├── flows/
│       │   │   ├── book.py       # Booking flow (CLARIFY_TIME, OFFER_ALTERNATIVES, …)
│       │   │   ├── cancel.py     # Cancellation flow
│       │   │   └── reschedule.py # Rescheduling flow
│       │   └── nlu/
│       │       ├── intents.py    # Deterministic intent detection
│       │       └── entities.py   # Slot extraction (date, time, phone, name, service)
│       ├── stt/
│       │   ├── faster_whisper_stt.py  # Production STT (loaded once)
│       │   └── fake_stt.py            # Test STT (queued strings / UTF-8 decode)
│       └── tts/
│           ├── edge_tts_engine.py     # Production TTS (8s timeout, None on failure)
│           ├── piper_engine.py        # Optional offline TTS
│           └── fake_tts.py            # Test TTS (deterministic bytes)
│
├── backend/                      # FastAPI server
│   └── app/
│       ├── main.py               # App factory + lifespan (loads Whisper once, sets app.state)
│       ├── config.py             # pydantic-settings (all env vars)
│       ├── schemas.py            # WS message Pydantic models
│       ├── api/
│       │   ├── ws_calls.py       # WebSocket /ws/calls (audio + text, rate limits, idle timeout)
│       │   ├── health.py         # GET /health  +  GET /api/health (with STT/TTS status)
│       │   ├── appointments.py   # REST CRUD
│       │   └── clinic.py         # GET /clinic
│       ├── db/
│       │   ├── models.py         # Appointment model with partial unique index
│       │   └── engine.py         # Async SQLAlchemy engine
│       ├── repositories/
│       │   └── appointments.py   # free_slots, create, cancel, reschedule, find_upcoming_by_phone
│       └── services/
│           ├── booking_gateway.py # SqlBookingGateway (sync adapter for brain)
│           ├── session_store.py   # In-memory TTL+LRU session store
│           └── clock.py           # SystemClock (injects real date/time)
│
├── frontend/                     # React + Vite (Phase 5)
├── scripts/
│   └── ws_smoke_test.py          # Manual WebSocket smoke test
├── DESIGN.md                     # State machine diagram + messy-case table
├── PLAN.md                       # Architecture specification
└── docker-compose.yml            # PostgreSQL + backend services
```

---

## Hard Rules (from `AGENTS.md`)

1. **No LLM anywhere in `ai-tool/`** — verified by AST scan in `test_no_llm.py`
2. **All reply text in `responses.py`** — single source of truth
3. **Clock injection** — `datetime.now()` never called inside the brain
4. **No PII in logs** — phone numbers are masked
5. **Dependency direction**: `frontend → backend → ai-tool` (ai-tool has no web/DB imports)
