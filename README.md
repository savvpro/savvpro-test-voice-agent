# Riverside Lost Property

A complete voice and text assistant for a fictional mall's lost-property desk.

**Speak → Groq Whisper large v3 → deterministic Python brain → browser text-to-speech.**

The assistant searches 24 fictional found items, asks distinguishing questions, handles corrections and uncertainty, and saves either a lost-item report or a claim pending staff review. Selecting a similar item never establishes ownership.

## Quick start with Docker

1. Copy .env.example to .env at this repository root and set GROQ_API_KEY.
   You can also keep the key in backend/.env; both Docker and local startup support that location.
2. Run:

~~~sh
docker compose up --build -d
~~~

3. Open http://127.0.0.1:8088.

The container applies migrations and idempotently seeds fictional inventory. Cases persist in a Docker volume. After changing .env, run docker compose up -d --force-recreate. The key remains on the server and is excluded from the image and Git.

## Run locally

Requires Python 3.14, Node.js 24, and npm 11. Run from this repository root:

~~~powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.lock
.venv/Scripts/python.exe -m pip install --no-deps --no-build-isolation -e backend
npm --prefix frontend ci --ignore-scripts
Copy-Item .env.example .env
# Set GROQ_API_KEY in .env, then:
.venv/Scripts/python.exe scripts/dev.py
~~~

On macOS/Linux use .venv/bin/python and cp instead of the Windows Python path and Copy-Item.

Open http://127.0.0.1:5173. Ctrl+C stops both local servers. The helper applies migrations and seeds the demonstration explicitly; subsequent starts preserve existing cases and inventory.

## Use the complete voice flow

1. Choose **Talk to the assistant** and consent to sending the recording to Groq.
2. Allow microphone access, speak, then choose **Finish recording**.
3. The server transcribes with whisper-large-v3. Our Python rules choose the next question; the browser reads it aloud.
4. Continue until the assistant asks permission to submit. Say **yes** to receive a saved reference.

Recording stops automatically after 60 seconds; uploads are limited to 8 MiB. Discard recording and Cancel transcription suppress late callbacks. Mute, replay, end conversation, and typed input remain available. Use localhost or HTTPS for microphone access.

Only English is supported by the first release. Browser speech-synthesis voices vary by operating system. No audio is persisted by this application. Audio is sent to Groq for recognition; no inventory or conversation state is sent to a model.

## Suggested demonstration

Use yesterday for freshly seeded inventory; if reusing an older database, use its original demonstration date.

~~~text
Caller: A black Jansport backpack with two compartments near the food court yesterday.
Assistant: Can you describe any distinctive marks, attachments, or something inside?
Caller: A yellow duck keychain.
Assistant: ... Shall I submit it?
Caller: Yes.
Assistant: Your reference is LF-... Your possible-match claim is pending staff review.
~~~

Also try:

- "Purple wallet with stars near the cinema yesterday" → no convincing match → confirmed lost report.
- "Actually, it was blue" → invalidates the old match and confirmation.
- "I don't know" → bounded clarification, then a report instead of an endless loop.
- "Option 2" → records a preference; identifying checks and staff review are still required.
- "Repeat", "help", "restart", or "cancel".
- Start a new search after completion; each search can create one outcome safely.

All people, records, and the mall are fictional. Do not provide real personal information.

## Architecture

- backend/src/lost_property/domain: explicit vocabulary, field extraction, weighted matching, question selection, identification, and dialogue states. No LLM or embeddings.
- application: transactional turn processing and the Groq audio adapter.
- persistence: SQLite repositories, migrations shipped with the Python package, and idempotent fixtures.
- frontend: React/TypeScript conversation, safe decision inspector, microphone recording, transcription upload, and text-to-speech.
- Generated OpenAPI types keep the client contract synchronized.

Read [DESIGN.md](DESIGN.md) for rules and tradeoffs and [CONSTRAINTS.md](CONSTRAINTS.md) for quality gates.

## Verification

From backend/ with the virtual environment active:

~~~sh
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest --cov=lost_property --cov-branch --cov-report=json --cov-report=xml --cov-fail-under=85
python scripts/check_domain_coverage.py --minimum 95
python -m pip_audit -r requirements.lock
python -m pip_audit -r requirements-dev.lock
python -m pytest tests/performance -m performance -s
~~~

The normal test run excludes the explicitly marked performance test: the 300 ms p95 release budget is measured separately on the local machine rather than enforced on noisy CI workers.

From frontend/:

~~~sh
npm run lint
npm run typecheck
npm run test:coverage
npm run api:check
npm run build
npm run check:bundle
npm audit --audit-level=high
npx playwright install chromium
npm run test:e2e
~~~

Browser tests run an isolated API/database and real Chromium audio recording. Billable STT and audible playback boundaries are controlled in automated tests; genuine provider and physical-microphone observations are recorded separately in docs/VERIFICATION.md. No test key contacts Groq.

## Maintenance and operating limits

Run python -m lost_property.cli cleanup daily from backend/, or docker compose exec app python -m lost_property.cli cleanup. Conversations and retry ledgers expire after 24 hours, with a 30-minute idle timeout; fictional cases expire after 30 days. Expiry is enforced on access and cleanup runs at startup, but long-running deployments must schedule daily cleanup.

This release supports one API worker with a durable SQLite volume. Before public multi-instance deployment, add authenticated staff workflows, shared throttling, HTTPS/secure-cookie configuration, and an appropriate operational retention policy. The assistant never releases property or promises ownership.

## Troubleshooting

- Voice unavailable: verify GROQ_API_KEY in root .env and restart the backend/container. The key must not use a VITE_ prefix.
- Microphone unavailable: use a current browser on localhost or HTTPS, check browser permissions and device selection, or type.
- No spoken reply: enable spoken replies or choose Replay reply; the transcript remains visible.
- 409 conflict: the client refreshes the current state; send the corrected message again.
- Provider limit or timeout: wait briefly and record again; the case is not changed by a failed transcription.
- Port occupied: scripts/dev.py accepts --backend-port and --frontend-port.
- Database not ready: run python -m lost_property.cli migrate from backend/.

## Assessment

[AI_USAGE.md](AI_USAGE.md) records development assistance and evidence limitations. The original assessment/submission instructions are preserved in [docs/ASSESSMENT_SUBMISSION.md](docs/ASSESSMENT_SUBMISSION.md).

All changes are deliberately uncommitted; the repository owner manages commits and submission.
