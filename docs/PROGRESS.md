# Implementation milestones

1. Foundation: modular FastAPI/SQLAlchemy/SQLite backend, Next.js frontend, configuration and usage log. Accept: imports/install succeed; assessment and candidate branch preserved.
2. Brain: ordered intent rules, explicit parsing, state transitions and contextual corrections. Accept: deterministic tests, ambiguous information cannot authorize a write.
3. Booking/API: availability, transaction-safe create/reschedule/cancel, idempotency. Accept: actual API workflows, conflict/concurrency and persistence tests.
4. Voice and interface: turn-based speech, typed fallback, real decision inspector. Accept: frontend production build, accessible interaction and clear failure states.
5. Quality/submission: docs, complete test run, secret/working-tree review. Accept: reproducible commands and candid limitations; no push/PR/deployment without user approval.

## Constraints

`TASK.md` is the source of truth and must remain untouched. Preserve `candidate-TUAHASHAIKH`. Synthetic data only. No runtime LLM, keys, auth, telephone integration or infrastructure beyond the requested stack. Explicit confirmation before booking/rescheduling/cancellation. No fabricated evidence.

## Status — 2026-10-26, Asia/Karachi

Implementation milestones 1–4 are complete. Milestone 5 automated checks and documentation are complete; physical voice verification and authentic AI usage evidence remain candidate actions before submission.

The backend persists appointments, sessions and turn receipts. One SQLite transaction per mutating turn protects both booking changes and their reported outcome. The interface includes turn-based browser voice, full typed fallback, actual decision metadata, booking confirmation/receipts, available starts, narrow-screen layouts and safe retries through reloads.

## Executed validation

| Check | Actual result |
| --- | --- |
| `.venv/Scripts/python -m pytest` | **82 passed**, one upstream Starlette TestClient/httpx deprecation warning; no failures |
| `npm run build` in frontend | Passed production compilation, type validation and static-page generation; Next.js 15.5.28 |
| `npm run typecheck` | Passed |
| `PLAYWRIGHT_CHANNEL=msedge npm run test:e2e` (PowerShell environment equivalent) | **6 passed**, using installed headless Edge and a real isolated fixed-clock backend |
| `npm audit --audit-level=high` | **0 vulnerabilities** after PostCSS 8.5.31 override |
| `.venv/Scripts/python -m pip check` | No broken requirements |
| `git diff --check` | Passed; Git emitted its normal Windows LF/CRLF notice |
| Source/documentation credential-pattern scan | 40 files scanned, 0 findings for private-key/OpenAI/AWS/GitHub credential patterns; this is a limited pattern check, not a security guarantee |
| Assessment preservation | `TASK.md` blob hash exactly matches HEAD; branch remains `candidate-TUAHASHAIKH` |

Backend tests include actual state transitions, relative/spoken date/time parsing, uncertainty, corrections, service duration, opening/closing boundaries, explicit confirmations, conflicts, two independent application instances confirming concurrently, repeated request receipts, stale revisions/appointment versions, isolation, persistence after restart, UTC storage, configured business timezone, rollback after simulated commit failure, and prevention of partial rescheduling after caught validation errors.

Browser tests cover typed booking with correction and raw trace, rescheduling/cancellation, a response intentionally lost after a real commit followed by reload/retry, mocked recognition/synthesis sequencing, unsupported voice/mobile overflow, and mocked microphone-permission denial with typed recovery. The production frontend and backend are real; only browser speech is mocked where explicitly noted. Desktop and 390-pixel mobile screenshots were generated and inspected. Test servers were stopped by suite teardown.

## Remaining manual actions and limits

- Run [DEMO_CHECKLIST.md](DEMO_CHECKLIST.md) with a real microphone and speakers in Chrome/Edge. Actual audio capture, recognition accuracy and audible playback were **not** physically verified by the coding agent.
- Fill [AI_USAGE.md](../AI_USAGE.md) with authentic token usage and logs/screenshots. This tool session exposes no reliable token meter; no values were invented.
- Review the submission and explicitly authorize pushing/opening the assessment PR when ready. The user authorized focused local commits after implementation; no push, PR or deployment was performed by the agent.
- The intentionally small English grammar and local-demo limitations are documented in README/DESIGN. The non-failing Starlette/httpx warning is from installed upstream test-client integration.

## Commit organization

At the user's request, the completed implementation is grouped into focused commits for the project setup, domain/configuration, persistence, language parser, state machine, booking operations, REST API, backend tests, frontend scaffold, typed API client, browser voice adapter, workspace interface, browser tests, and documentation. These commits are assembled after development, with their actual creation timestamps; they are not a chronological record of the original implementation sessions.
