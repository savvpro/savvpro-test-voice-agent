# Assessment engineering rules

## Non-negotiable requirements
- Runtime intent detection, entity extraction, dialogue policy, and response generation make ZERO LLM calls. All decisions use our Python rules and state machine. Groq Whisper is permitted only for speech transcription.
- Python backend; React/TypeScript frontend. Preserve TASK.md and implement booking, rescheduling, cancellation, voice input/output, and actual decision visibility.
- Use fake data only. Alex Rivera is fictional. Never collect real contact, registration, or payment details.
- Never commit secrets, .env files, local databases, raw audio, or unsanitized assistant session logs. Browser code must never receive provider/database credentials.
- Keep README.md, DESIGN.md, AI_USAGE.md, sanitized usage evidence, and tests accurate. Record observed AI mistakes and verification limitations; never invent token counts, claims, or test results. Export token_count metadata only; do not sum cumulative totals.

## Architecture and correctness
- SQLAlchemy 2.0 supports sqlite:///./workshop.db and DATABASE_URL for Postgres. Initialize with Base.metadata.create_all in FastAPI lifespan; no Alembic, automatic drops, or destructive schema upgrades.
- One worker. Every browser session owns an isolated two-bay simulation. Reset and appointment access must remain session-scoped.
- Allocation uniqueness is enforced by UniqueConstraint("bay_id", "segment_start"). Every service segment occupies the same bay. Reserve, cancel, and reschedule atomically; failures must preserve existing appointments.
- Persist turn_id deduplication with the turn's mutations. Reject stale revisions, including requests arriving after reset. Edits invalidate confirmation.
- Ask which appointment when multiple owned appointments match. Background occupancy is never caller-owned.
- Dates use Asia/Karachi and an injectable clock. Persist normalized UTC instants. Never seed a booking outside opening hours.
- Browser recognition is primary; /api/stt is an optional transcription-only fallback. Use one turn pipeline for speech, chips, and typing.
- TTS completion must run exactly once, including watchdog expiry (maximum 12 seconds), interruption, errors, and late events. Stop recognition during synthesis; clean up microphone resources.

## Delivery and checks
- Work on candidate-Farukhthegreat. origin is Farukhthegreat/savvpro-test-voice-agent; upstream is savvpro/savvpro-test-voice-agent.
- Prioritize comprehensive pytest brain/API/transaction tests, including Postgres parity. Frontend uses focused Vitest/state tests and build/smoke checks; actual microphone speech is verified in desktop Chrome.
- Commands: uv run pytest; uv run ruff check .; uv run mypy backend; npm --prefix frontend run check; npm --prefix frontend run test; npm --prefix frontend run build.
- Do not claim manual voice, Groq, Postgres, hosting, or Docker verification unless actually performed. Keep an explicit verification record.
- Submission deadline: 2026-10-27 00:00 Asia/Karachi. Reserve the final hour for deployment, documentation, walkthrough, and PR submission.
