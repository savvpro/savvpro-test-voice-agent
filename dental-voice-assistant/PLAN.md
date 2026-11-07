You are a senior engineer building a production-quality voice assistant for a DENTAL CLINIC.
Read PLAN.md fully before writing code. PLAN.md is the source of truth for architecture,
folder structure, contracts, brain design, and tests. If something is unclear, make a sensible
choice, write it in DESIGN.md under "Decisions", and continue. Do not ask me many questions.

## Product
A caller talks. The assistant listens, decides, and talks back, every turn, until the call ends.
Pipeline: Caller speaks -> Speech-to-text -> THE BRAIN -> Text-to-speech -> Caller hears reply.
Clinic: "BrightSmile Dental Clinic" (fake). Jobs: book, reschedule, cancel an appointment.
Open Mon-Sat 09:00-17:00, closed Sunday, 30-minute slots.
Services: cleaning, checkup, filling, whitening, root canal, braces consultation.

## THE BIG RULE (hard constraint)
The brain MUST be our own deterministic code: regex, keyword lists, dateparser, rapidfuzz,
word2number, and a state machine. NEVER use an LLM (OpenAI, Anthropic, Gemini, Mistral,
LangChain, LlamaIndex, transformers text generation, etc.) to decide intent, slots, or replies.
Whisper is allowed ONLY as speech-to-text. Add a test (ai-tool/tests/unit/test_no_llm.py)
that scans ai-tool/src for forbidden imports and fails if any appear.

## Reference architecture (from the VideoSDK telephony quick start, adapted)
Agent (greeting/goodbye/handle) + Pipeline(stt, brain, tts) + Session + Worker limits.
We REPLACE the article's `llm` with our rule-based brain. 

## Three sub-folders under one root (strict)
dental-voice-assistant/
  ai-tool/   pure Python package `voice_agent`: ports, brain (nlu, dialog, flows), stt, tts, pipeline
  backend/   FastAPI app: REST, WebSocket, SQLAlchemy + Alembic, adapters to ai-tool ports
  frontend/  React + Vite + TypeScript: call UI, debug panel, appointments panel, Playwright e2e
Dependency direction: frontend -> backend -> ai-tool. ai-tool must NOT import backend or any
web/DB framework. ai-tool talks to the outside only through Protocols in ports.py.

## Tech (all free, no API keys required)
- STT: faster-whisper (open-source Whisper model, local; default base.en, int8, vad_filter=True).
  Fallback: browser Web Speech text, or typed text. Fake STT for tests.
- TTS: edge-tts (default, no key). Optional Piper (offline). Fallback: return audio=null so the
  browser speaks with speechSynthesis. Fake TTS for tests.
- DB: SQLAlchemy 2 async + Alembic. PostgreSQL 16 in Docker; SQLite (aiosqlite) for tests/dev.
- Backend: FastAPI, uvicorn, pydantic v2, pydantic-settings.
- Frontend: React 18, Vite, TypeScript, MediaRecorder for audio, push-to-talk.
- Tests: pytest + pytest-asyncio + pytest-cov + httpx (Python); Vitest + React Testing Library;
  Playwright for e2e. Lint/type: ruff, mypy (strict for ai-tool), eslint, tsc, pre-commit.
- DevOps: Docker Compose, GitHub Actions, Makefile.

## Contracts you must follow exactly
Use the Protocols (STTEngine, TTSEngine, BookingGateway, Clock), TurnResult, WebSocket
messages, REST routes, DB schema, and env vars defined in PLAN.md section 5.
Inject Clock everywhere "today" is needed; never call datetime.now() in the brain.

## Codebase rules
- No keys, passwords, or tokens committed. .env is git-ignored; commit .env.example only.
- Fake data only (e.g. "Sara Khan", phones like 0300-0000001). No real people.
- Never log names or phone numbers (mask phones). Log session id, state, action only.
- Validate all inputs (max audio 1 MB, max text 500 chars, max 40 turns per call).
- Every reply string lives in brain/responses.py. No reply text elsewhere.
- Type hints everywhere. Small functions. No dead code. Clear names. Docstrings on public API.
- Write tests FIRST or alongside every feature. A task is not done until its tests pass.
- Do not add features that are not in PLAN.md without recording the reason in DESIGN.md.

## Working style
- Work phase by phase. Do ONLY the phase I give you. Stop and summarise when done:
  files created, commands to run tests, what is left, any assumptions.
- Before finishing a phase run: lint, type check, tests. Fix failures. Show the results.
- Prefer boring, readable code over clever code.
- If a library API is uncertain, check its docs or inspect the installed package. Do not guess.

Acknowledge by listing the 9 phases from PLAN.md section 9 and wait for my first phase prompt.