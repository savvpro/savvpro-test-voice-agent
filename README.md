# 🦷 City Dental Clinic – Voice AI Appointment Agent

A fully **local** voice AI agent that handles dental clinic appointment booking via natural conversation — no cloud APIs, no paid keys, everything runs on your own machine.

Built as a full-stack solution with a **FastAPI WebSocket backend** (Python) and a **Next.js frontend** (TypeScript/React).

---

## ✨ Features

| Feature | Details |
|---|---|
| 🎙️ Speech-to-Text | `faster-whisper` (base.en model, CPU int8) — fully offline |
| 🔊 Text-to-Speech | Piper TTS (`en_US-lessac-medium`) — fully offline |
| 🧠 Conversation Brain | Rule-based Intent-first FSM with mid-flow correction handling |
| 📅 Appointment Booking | Name · Doctor · Date · Time · Visit Reason collection |
| 🔄 Corrections | Natural mid-flow slot corrections ("Actually, make it Tuesday at 3pm") |
| 📞 Reschedule / Cancel | Full flows with confirmation steps |
| ⚠️ 3-Strikes Handover | Hands off to human agent after repeated misunderstandings |
| 🌐 Real-time Frontend | Next.js UI with audio visualizer, push-to-speak, slot inspector |
| ✅ Test Suite | 126 unit + E2E tests — all passing |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Next.js Frontend (3000)                │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Mic Rec. │  │ Audio Visual │  │  Slot Inspector   │  │
│  │ (WebAudio│  │ (16 bands)   │  │  FSM State Badge  │  │
│  │  API)    │  └──────────────┘  └───────────────────┘  │
│  └────┬─────┘                                            │
└───────┼─────────────────────────────────────────────────┘
        │  WebSocket ws://localhost:8000/ws
        │  (binary WAV frames ↑ / JSON+base64 audio ↓)
┌───────┼─────────────────────────────────────────────────┐
│       ▼           FastAPI Backend (8000)                 │
│  ┌─────────┐  ┌──────────────────────────────────────┐  │
│  │ Whisper │  │             FSM Brain                │  │
│  │  STT    │→ │  intents.py → slots.py → fsm.py      │  │
│  └─────────┘  │  availability.py  responses.py       │  │
│               └──────────────┬───────────────────────┘  │
│  ┌─────────┐                 │                           │
│  │  Piper  │←────────────────┘                           │
│  │   TTS   │  (text response → WAV bytes → WS send)      │
│  └─────────┘                                             │
└─────────────────────────────────────────────────────────┘
```

---

## 🗂️ Project Structure

```
savvpro-test-voice-agent/
├── backend/
│   ├── brain/
│   │   ├── availability.py   # Mock Mon-Fri availability grid (28 weekdays)
│   │   ├── fsm.py            # Main conversation state machine
│   │   ├── intents.py        # Priority-ordered regex intent classifier
│   │   ├── responses.py      # Speech response templates
│   │   ├── slots.py          # Slot extractor (name/doctor/date/time/reason)
│   │   ├── stt.py            # faster-whisper STT integration
│   │   └── tts.py            # Piper TTS integration
│   ├── models/
│   │   └── en_US-lessac-medium.onnx.json   # Piper voice config
│   │   # en_US-lessac-medium.onnx          # (gitignored, download separately)
│   ├── scripts/
│   │   ├── download_piper_model.py  # One-time model download helper
│   │   └── test_client.py           # Interactive terminal WebSocket client
│   ├── tests/
│   │   ├── test_corrections.py  # 17 correction-flow tests
│   │   ├── test_e2e.py          # 5 end-to-end scenario tests
│   │   ├── test_fsm.py          # 10 FSM lifecycle tests
│   │   ├── test_intents.py      # 48 intent classification tests
│   │   ├── test_slots.py        # 24 slot extraction tests
│   │   ├── test_stt.py          # 3 STT unit tests
│   │   └── test_tts.py          # 3 TTS unit tests
│   ├── main.py              # FastAPI app entry point
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx         # Main voice agent UI
│   │   │   ├── layout.tsx       # Dark theme root layout
│   │   │   └── globals.css      # Custom animations
│   │   └── types/
│   │       └── agent.ts         # TypeScript interfaces
│   ├── package.json
│   ├── next.config.mjs
│   └── tailwind.config.ts
├── docs/
│   ├── DESIGN.md        # Intent-first FSM design document
│   └── AI_USAGE.md      # AI tool usage log (per TASK.md requirement)
└── TASK.md              # Original task specification
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+** (tested on 3.14)
- **Node.js 18+** and npm
- ~500MB disk space for AI models

---

### 1. Clone & Setup Backend

```bash
# Clone the repo
git clone https://github.com/irasheedahmed/savvpro-test-voice-agent.git
cd savvpro-test-voice-agent
git checkout candidate-irasheedahmed

# Create and activate virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS

# Install Python dependencies
pip install -r backend/requirements.txt
```

### 2. Download AI Models

**Whisper STT** — downloaded automatically on first use from HuggingFace.

**Piper TTS** — run the helper script once:

```bash
python backend/scripts/download_piper_model.py
```

This downloads `en_US-lessac-medium.onnx` (~63 MB) into `backend/models/`.

### 3. Start the Backend

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

Backend is ready when you see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

Verify with: `http://localhost:8000/health` → `{"status":"ok"}`

### 4. Start the Frontend

Open a **new terminal**:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** in your browser.

---

## 🎮 Using the App

1. Click **"Start Call"** — connects to the backend WebSocket
2. Hold **"Push to Speak"** and say something like:
   - *"I'd like to book an appointment"*
   - *"Dr. Khan on Monday at 3pm"*
   - *"Actually, make it Tuesday instead"*
3. The agent responds via **text + synthesized voice**
4. Watch the **Brain Slots** panel fill up as information is collected
5. Confirm when prompted → **🎉 booking confirmed!**

**Text fallback:** Type messages in the input box if mic isn't available.

---

## 🧪 Running Tests

```bash
# From repo root
python -m pytest backend/tests -v

# Expected: 126 passed
```

Individual test files:

```bash
python -m pytest backend/tests/test_intents.py -v      # 48 intent tests
python -m pytest backend/tests/test_slots.py -v        # 24 slot tests
python -m pytest backend/tests/test_corrections.py -v  # 17 correction tests
python -m pytest backend/tests/test_fsm.py -v          # 10 FSM tests
python -m pytest backend/tests/test_e2e.py -v          # 5 E2E scenarios
python -m pytest backend/tests/test_stt.py -v          # 3 STT tests
python -m pytest backend/tests/test_tts.py -v          # 3 TTS tests
```

---

## 🔌 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check → `{"status":"ok"}` |
| `/ws` | WebSocket | Main conversation endpoint |
| `/api/stt` | POST | Upload audio file → `{"text":"..."}` |
| `/api/tts` | POST | JSON `{"text":"..."}` → WAV audio bytes |

### WebSocket Protocol

**Send (client → server):**
- `text:Hello` — text message
- `base64:<b64-encoded-wav>` — audio frame
- Binary WAV bytes directly

**Receive (server → client):**
```json
{
  "type": "response",
  "text": "What name should I put on the appointment?",
  "audio": "<base64-wav>",
  "state": "COLLECT_NAME",
  "slots": { "name": null, "doctor": "Dr. Khan", "date": null, "time": null, "reason": null },
  "done": false
}
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|---|---|---|
| `WHISPER_MODEL` | `base.en` | Whisper model size (tiny/base/small/medium) |
| `WHISPER_DEVICE` | `cpu` | Device for Whisper (`cpu` or `cuda`) |
| `PIPER_MODEL_PATH` | `models/en_US-lessac-medium.onnx` | Path to Piper ONNX model |

Set in a `.env` file in `backend/` or export before starting uvicorn.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **STT** | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 1.2.1 (CTranslate2 backend) |
| **TTS** | [piper-tts](https://github.com/rhasspy/piper) 1.8.0 + ONNX Runtime |
| **NLU** | Rule-based intent classifier + regex slot extractor (no LLM) |
| **Backend** | FastAPI + Uvicorn + python-multipart |
| **Frontend** | Next.js 14 + React 18 + TailwindCSS 3 + TypeScript |
| **Testing** | pytest 8.x |

---

## 📋 FSM States

```
GREETING → COLLECT_NAME → COLLECT_DOCTOR → COLLECT_DATE → COLLECT_TIME
        → COLLECT_REASON (optional) → CONFIRM_BOOKING → BOOKED
                                    → RESCHEDULE_FLOW
                                    → CANCEL_CONFIRM → CANCELLED
                                    → HANDOVER (3-strikes)
```

---

## 🧠 Design Decisions

See [`docs/DESIGN.md`](docs/DESIGN.md) for the full design document covering:

- **Intent-first architecture** — classify intent before slot extraction to handle corrections naturally
- **Correction handler** — dedicated `_handle_correction` method updates any slot mid-flow
- **Priority-ordered intent matching** — GOODBYE > CANCEL > RESCHEDULE > CORRECTIONS > CONFIRM/DENY > BOOK > PROVIDE_INFO
- **Mock availability grid** — 28 weekdays Mon-Fri with open/closed slots per doctor

---

## 📝 AI Usage

See [`docs/AI_USAGE.md`](docs/AI_USAGE.md) for a full log of AI tool usage, what it got right, and where human correction was required.

---

## 👤 Author

**Irasheed Ahmed** — `candidate-irasheedahmed`
Built for the SAVV Pro Solutions Voice Agent Assessment.
