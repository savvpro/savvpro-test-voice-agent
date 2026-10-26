# Deterministic Automotive Service Voice Assistant

A production-style assessment demo that books a fictional automotive service appointment by voice or text. The Python brain is a deterministic finite-state workflow: it does not call an LLM.

## What it demonstrates

- Push-to-talk speech input and browser text-to-speech
- Text fallback for unsupported/denied microphone access
- A visible decision panel with state, action, reason, accepted values, and draft
- Corrections, bounded retries, relative dates, ambiguous-time clarification, alternatives, and explicit confirmation
- Capacity-aware, single-process booking with idempotent turns and optimistic session versions
- Fake, ephemeral data only

## Run locally

Requirements: Python 3.12+, Node.js 20+, and Chrome or Edge for the voice demo.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --app-dir backend --reload
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The UI proxies API calls to `http://localhost:8000`.

## Test and verify

```bash
pytest
ruff check backend
cd frontend
npm run lint
npm run build
```

Backend container smoke test:

```bash
docker build -t savvpro-voice-agent .
docker run --rm -p 8000:8000 savvpro-voice-agent
curl http://localhost:8000/health
```

## Demo script

1. Start a session and say/type `Sara Khan`.
2. Enter `555 123 4567`.
3. Continue with `2021`, `Toyota Corolla`, and `oil change`.
4. Say `tomorrow`, then `at 4` to see deterministic clarification.
5. Enter `4 pm`; review the visible decision and summary.
6. Say `yes`; retrying the same HTTP turn cannot create a second booking.

Try `cancel the oil change, I want a tire rotation`, a taken slot, `start over`, or a bare `yes` at the wrong time.

## Explicit limits

This is an assessment demo, not a production deployment. Storage is in memory, is lost on restart, and protects against double booking only inside one Python process. Run one backend worker. Browser STT availability varies and may use a browser vendor's network service; text input exercises the exact same brain.

See [DESIGN.md](DESIGN.md), [PLAN.md](PLAN.md), and [AI_USAGE.md](AI_USAGE.md).
