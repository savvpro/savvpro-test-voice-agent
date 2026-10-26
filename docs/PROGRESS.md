# Implementation milestones

1. Foundation: modular FastAPI/SQLAlchemy/SQLite backend, Next.js frontend, configuration and usage log. Accept: imports/install succeed; assessment and candidate branch preserved.
2. Brain: ordered intent rules, explicit parsing, state transitions and contextual corrections. Accept: deterministic tests, ambiguous information cannot authorize a write.
3. Booking/API: availability, transaction-safe create/reschedule/cancel, idempotency. Accept: actual API workflows, conflict/concurrency and persistence tests.
4. Voice and interface: turn-based speech, typed fallback, real decision inspector. Accept: frontend production build, accessible interaction and clear failure states.
5. Quality/submission: docs, complete test run, secret/working-tree review. Accept: reproducible commands and candid limitations; no push/PR/deployment without user approval.

## Constraints

`TASK.md` is the source of truth and must remain untouched. Preserve `candidate-TUAHASHAIKH`. Synthetic data only. No runtime LLM, keys, auth, telephone integration or infrastructure beyond the requested stack. Explicit confirmation before booking/rescheduling/cancellation. No fabricated evidence.

## Status — 2026-10-26, Asia/Karachi

Implementation milestones 1–4 are complete. Milestone 5 automated checks and documentation are complete; authentic AI usage evidence has been added; physical voice verification remains a candidate action before submission.

The backend persists appointments, sessions and turn receipts. One SQLite transaction per mutating turn protects both booking changes and their reported outcome. The interface includes turn-based browser voice, full typed fallback, actual decision metadata, booking confirmation/receipts, available starts, narrow-screen layouts and safe retries through reloads.

## Executed validation

| Check | Actual result |
| --- | --- |
| `.venv/Scripts/python -m pytest` | **274 passed** after six spoken-conversation follow-ups, one upstream Starlette TestClient/httpx deprecation warning; no failures |
| `npm run build` in frontend | Passed production compilation, type validation and static-page generation; Next.js 15.5.28 |
| `npm run typecheck` | Passed |
| `PLAYWRIGHT_CHANNEL=msedge npm run test:e2e` (PowerShell environment equivalent) | **6 passed**, using installed headless Edge and a real isolated fixed-clock backend |
| `npm audit --audit-level=high` | **0 vulnerabilities** after PostCSS 8.5.31 override |
| `.venv/Scripts/python -m pip check` | No broken requirements |
| `git diff --check` | Passed; Git emitted its normal Windows LF/CRLF notice |
| Source/documentation credential-pattern scan | 46 text files scanned after adding usage evidence, 0 findings for private-key/OpenAI/AWS/GitHub credential patterns; this is a limited pattern check, not a security guarantee |
| Assessment preservation | `TASK.md` blob hash exactly matches HEAD; branch remains `candidate-TUAHASHAIKH` |

Backend tests include actual state transitions, relative/spoken date/time parsing, uncertainty, corrections, service duration, opening/closing boundaries, explicit confirmations, conflicts, two independent application instances confirming concurrently, repeated request receipts, stale revisions/appointment versions, isolation, persistence after restart, UTC storage, configured business timezone, rollback after simulated commit failure, and prevention of partial rescheduling after caught validation errors.

Browser tests cover typed booking with correction and raw trace, rescheduling/cancellation, a response intentionally lost after a real commit followed by reload/retry, mocked recognition/synthesis sequencing, unsupported voice/mobile overflow, and mocked microphone-permission denial with typed recovery. The production frontend and backend are real; only browser speech is mocked where explicitly noted. Desktop and 390-pixel mobile screenshots were generated and inspected. Test servers were stopped by suite teardown.

## Follow-up: real spoken-conversation feedback

The user's transcript exposed narrow booking phrases, filler words included in names, generic recovery after a misheard booking request, and loss of a known reference during rescheduling. Added 35 regression cases, including the complete reported conversation, directional time changes, status questions, legacy session-reference recovery, session isolation, explicit-reference priority, negation, draft cancellation safety, and protection against restoring rejected dates/times. The initial targeted suite reproduced 24 failures before the fixes; the final full backend run passed all 117 cases. Frontend typecheck passed with the extended session contract.

The follow-up retains a session's last verified reference, supports ordinary booking requests, asks targeted clarification after unclear availability follow-ups, cleans bounded name fillers, and selects brief topic-specific business replies. All booking writes still require explicit confirmation. No LLM or fuzzy transcription-to-action guess was introduced.

The earlier production build and six browser-test results above predate this follow-up. The user had running app servers on ports 3000/8000; those were preserved, and the browser suite was not rerun against its conflicting default ports. The new spoken-conversation cases exercise the actual HTTP API and database with an isolated fixed clock. Frontend executable behavior was unchanged; its session type gained the remembered reference field.

## Second follow-up: incomplete time claims and availability handoff

The next transcript exposed “around 40” being ignored during availability, “Yes do it at 4:30 PM” losing the selected time, “I said yes book it” failing intent recognition, spaced “4 30 PM to 5 30 PM” failing extraction, and “Make a new booking” being rejected after cancellation. Added 39 cases, including the full conversation through booking, rescheduling, cancellation and a separate new booking. The initial targeted run reproduced 25 failures; 5 of its initial 30 cases already passed. The final full suite passed **156 tests**.

The fix normalizes bounded repair prefixes consistently, supports spaced hour/minute tokens, rejects unparsed numeric time claims, and merges/rechecks details supplied after availability. Affirmatives with changed details never directly commit a write; exact matching affirmative action phrases can confirm an already complete proposal. New tests also protect against stale availability, compound action authorization, negation, name pollution and repaired cancellation targeting an older booking. Garbled services/actions remain clarification cases rather than guessed commands.

One intermediate Pytest attempt failed with a transient MemoryError during import/error reporting; a direct backend import succeeded and subsequent targeted/full runs completed. An early assertion also expected an internal confirmation rule instead of the public `commit.confirmed` decision; it was corrected to assert the actual API decision and `CONFIRM` intent. No frontend code or dependencies changed in this follow-up. The user's running app servers were preserved, and browser/audio checks were not rerun.

## Third follow-up: calendar-date grammar

The third transcript exposed unsupported "28th of October 2026", year-first month names, compact/spaced year-first digits, and malformed date numbers being mistaken for clock times. Added `calendar_dates.py` to recognize and mask complete calendar spans before time parsing. Invalid/incomplete date spans are also masked, so "2026 0 to 10" asks for a date while preserving the previously collected time. Named dates with no year use the business clock's current year; explicit incomplete or fully word-spoken years are clarified. Past-date rejection includes the exact interpreted date, so "2026 October 10" is visibly understood and rejected as past under the fixed October 26 test clock.

Added 46 cases covering the reported conversation/recovery, named-month orderings, ordinal words, year-first numeric forms, dates with separate times, leap years, invalid dates, mismatched weekdays, compound requests, conflict revalidation and fresh confirmation. The initial targeted suite reproduced 35 failures with 2 passing cases; the final full backend run passed **202 tests**. No frontend code/dependencies changed, and existing browser/audio results remain historical. `TASK.md` and the candidate branch were preserved.

## Fourth follow-up: spoken name instructions

The user reported that "Use name Taha" became the stored customer name "Use Name Taha". Added 32 regression cases covering explicit request wrappers, courtesy/repair prefixes, bare names, Unicode names, apostrophes/hyphens, missing values, unrelated commands and alternatives. The initial targeted run reproduced 19 failures, with 13 cases already passing. An anchored name grammar now extracts the value before validation; bare-name fallback remains restricted to the name-collection context. API/database regressions verify the reported booking stores only "Taha", and changing a pending name still requires fresh confirmation.

The final full backend suite passed **234 tests**. No frontend code or dependencies changed, existing stored appointments were not rewritten, and physical speech/browser checks were not rerun. The deterministic-brain rule, assessment file and candidate branch were preserved.

## Fifth follow-up: inline names and independent field repair

The next transcript supplied "with the name Muhammad Taha" alongside a malformed date and a valid time, but the parser discarded the name. Explicit name clauses are now consumed before service/calendar/time extraction and retain their own value when another field needs clarification. The malformed "428th" is still rejected. After correcting the date and choosing "Haircut plus beard", the reported flow reaches confirmation with the original name and time. "You should use Muhammad" updates the pending name without committing. A bounded name-reminder phrase reports only the current draft's name, or candidly asks for one when missing.

Added 30 regression cases, including the actual conversation through persistence, inline name orderings, invalid date/time recovery, names that overlap catalog/calendar words, conflicting or negated name corrections and new-booking name isolation. The initial 24-case targeted run reproduced 16 failures, with 8 cases already passing. The final full backend suite passed **264 tests** with one upstream warning. No frontend/dependency changes, database rewrites or browser/audio reruns occurred. The assessment and candidate branch remain unchanged.

## Sixth follow-up: name prepositions and occupied slots

The transcript's "for the name Muhammadaha" was unsupported, so no name was available after the occupied-time rejection. Shared name-preposition grammar now supports "for [the] name" and "with [the] name" in both booking requests and separate answers. The original transcribed spelling is retained until explicitly corrected; changing the time does not discard it. Added 10 cases, including the reported conversation with a real occupied slot and a second conflict before selecting another time. Tests verify fresh confirmation, the final saved name/time and preservation of the original conflicting appointment. The initial targeted run reproduced 8 failures with 2 passing cases; the full backend suite passed **274 tests**. Frontend/dependencies and the demo database were unchanged; browser/audio checks were not rerun.

## Remaining manual actions and limits

- Run [DEMO_CHECKLIST.md](DEMO_CHECKLIST.md) with a real microphone and speakers in Chrome/Edge. Actual audio capture, recognition accuracy and audible playback were **not** physically verified by the coding agent.
- Review the authentic screenshot and filtered local-session token counters in [AI_USAGE.md](../AI_USAGE.md), recorded on 2026-10-26 at 17:36:04 PKT. The snapshot covers 20 project commits; append later usage separately if needed. No quota percentage was converted into token counts.
- Review the submission and explicitly authorize pushing/opening the assessment PR when ready. The user authorized focused local commits after implementation; no push, PR or deployment was performed by the agent.
- The intentionally small English grammar and local-demo limitations are documented in README/DESIGN. The non-failing Starlette/httpx warning is from installed upstream test-client integration.

## Commit organization

At the user's request, the completed implementation is grouped into focused commits for the project setup, domain/configuration, persistence, language parser, state machine, booking operations, REST API, backend tests, frontend scaffold, typed API client, browser voice adapter, workspace interface, browser tests, and documentation. These commits are assembled after development, with their actual creation timestamps; they are not a chronological record of the original implementation sessions.
