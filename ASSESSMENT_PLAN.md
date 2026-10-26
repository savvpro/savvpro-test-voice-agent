# Assessment execution plan

Deadline: 27 October 2026, 00:00 PKT. Final hour reserved for release and submission.

1. Fork/clone, verify remotes and candidate branch, write AGENTS.md, establish isolated Python environment and lockfiles.
2. Implement SQLAlchemy 2.0 models, create_all lifespan initialization, SQLite/Postgres engines, per-browser isolated bays, idempotent fixtures and reset. Allocation uniqueness: (bay_id, segment_start). Caller seed: Alex Rivera, SUV, tyre rotation, next open day at 11:00. Background fixtures include both bays full and a valid 17:30 slot.
3. Build a deterministic Python NLU/state machine for book/reschedule/cancel, dates, synonyms, negation, corrections, confirmation invalidation, and 0/1/multiple appointment selection. Test before connecting UI.
4. Add cookie-owned sessions, turn_id deduplication, revision checks, transactional rescheduling/cancellation, and structured decision traces. Test collisions and reset races on SQLite and Postgres.
5. Build premium React reception: transcript, booking details, actual decision inspector, typed input, quick utterances, session reset. Browser speech primary; MediaRecorder plus /api/stt Groq Whisper fallback. Synthesis flush, word-count watchdog <=12 seconds, short chunks, exactly-once guarded completion and resource cleanup.
6. Verify with pytest as primary budget, focused frontend Vitest/check/build and browser smoke. Manually verify actual Chrome speech; record any unavailable credentials or hardware checks honestly.
7. Deploy both layers together on Render with Neon. Complete README, DESIGN, AI_USAGE and sanitized token evidence, walkthrough, push, upstream PR.

All core assessment requirements remain mandatory. No runtime LLM decisions, real personal data, or committed secrets. create_all is initialization, not schema migration. Independent demo workshops allow predictable session-local reset without modifying another reviewer’s state.

## Progress

- Repository, rules, environment, backend, interface, and assessment documentation implemented.
- 100 pytest cases pass across SQLite and Postgres on Windows; preceding 98-test suite passed on Linux; backend coverage 91%. Type/lint and production build pass. 28 Vitest tests pass on Windows; preceding 10-test suite passed on Linux.
- Actual API browser smoke and desktop/mobile render checks pass. Independent UI finish-review disposition: ship.
- Docker build and non-root runtime verified. Confirmed booking and revision persist across a container restart with Postgres.
- Candidate's first Chrome check: correct recognition, audible replies, fast responses; requested voice/cadence improvements have been implemented and need rechecking.
- Neon production branch linked/deployed and real API/database workflow verified. Required PR opened: https://github.com/savvpro/savvpro-test-voice-agent/pull/3.
- Public Render app verified: https://savvpro-test-voice-agent.onrender.com. Hosted browser workflows and actual Neon records pass; HTTPS/session cookie checks pass.
- Current runtime aa1c645 is deployed and its hosted workflow/reveal checks pass; the candidate confirms spoken chip replies and progressive text in Chrome.
- Remaining human check: final hosted microphone/cadence preference. Optional Groq remains unconfigured and is not claimed as live-verified. Evidence and submission are updated.
- Hosting: original Render workspace suspended; Railway signup unavailable. Candidate is configuring an available Google-login Render account using the public candidate branch. GitHub-hosted Actions cannot start because of an account billing lock; equivalent Linux-container checks are recorded separately.

## User-requested interface revision

Black/charcoal and brass gold replace the white/blue world. SVG icons and favicon, self-hosted Manrope, service shortcuts, visible mobile navigation, and a dedicated appointments view are implemented. Appointment actions pass the selected reference through the same deterministic confirmation flow. Initial transcript scrolling remains local, and Type instead exposes the non-microphone path. Desktop/mobile real-Neon workflows and 16 frontend tests pass; the fresh finish-review disposition is ship. Revision `591f3f1` is pushed and automatically deployed by Render. Its new asset fingerprint and complete hosted browser workflow pass; the new UI is public.

Test-drive playback/reveal: UI turns now speak outside microphone calls, late playback is generation-guarded, playback failures expose replay recovery, and new actual text has a bounded reduced-motion-safe word reveal. Runtime `aa1c645` is deployed; its fingerprint and hosted appointment/reveal/reduced-motion smoke pass. The candidate confirms audible one-shot replies and progressive text in desktop Chrome.

Confirmed schedule updates: the card, list and count use the committed response immediately, independent of speech completion. A visible status identifies the modified booking. All 28 frontend tests and local desktop/mobile API workflows pass, including preservation before confirmation/on failed reschedule; runtime `ca00faf` is deployed and its hosted desktop/mobile update checks pass.
