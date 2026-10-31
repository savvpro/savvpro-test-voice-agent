# Voice Agent — Clinic Appointment Booking Assistant

> **Local-only build. No cloud API keys required. No deployment.**

---

## Project Overview

A fully local voice assistant for booking, rescheduling, and cancelling clinic/dentist appointments. Built as an assessment submission for SAVV Pro Solutions.

**Tech Stack:**

| Component | Technology |
|---|---|
| Frontend | Next.js + TailwindCSS |
| Backend | Python FastAPI (WebSocket) |
| STT | faster-whisper (local) |
| Brain | Custom rule-based: regex intent matcher + FSM |
| TTS | Piper (local) |

---

## Local Development — No Keys Needed

This project is **fully local**. There are no cloud services, no API keys, and no `.env` secrets required. Everything runs on your machine.

---

## Project Structure

```
savvpro-test-voice-agent/
├── frontend/          # Next.js app — mic capture, WebSocket client, UI
├── backend/           # Python FastAPI — STT → brain → TTS pipeline
├── docs/
│   ├── DESIGN.md      # Brain FSM design, intent/slot definitions
│   └── AI_USAGE.md    # AI tool usage log
├── PLAN.md            # Build plan / phases
└── README.md          # This file
```

---

## Setup & Run Instructions

_(To be filled in — Phase 8)_

### Prerequisites

- Python 3.10+
- Node.js 18+
- [faster-whisper](https://github.com/guillaumekyn/faster-whisper)
- [Piper TTS](https://github.com/rhasspy/piper)

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Design

See [`docs/DESIGN.md`](docs/DESIGN.md) for the full FSM design, intents, slots, and correction-handling logic.

---

## AI Usage

See [`docs/AI_USAGE.md`](docs/AI_USAGE.md) for a full log of AI tool usage, what was helpful, and where corrections were needed.

---

## Assessment Submission Instructions

See the original submission guide: [`docs/SUBMISSION.md`](docs/SUBMISSION.md)
