# Verification record

Recorded 2026-10-26. All work remains uncommitted at the user's request.

## Observed results

- Backend: 92 tests passed; the separately marked performance test was deselected from the normal suite. Overall branch-aware coverage 89.17%; domain coverage 98.73% against the 95% gate.
- Frontend: 40 tests passed. Coverage: statements 95.03%, branches 80.23%, functions 97.50%, lines 97.41%; all configured gates passed.
- Browser: nine Playwright tests passed in Chromium, including claim/report/correction/isolation, the complete recorded-audio flow, and axe/layout checks at 390/768/1440 pixels. Zero serious/critical accessibility findings in tested initial states.
- Browser screenshots are local artifacts under .artifacts/browser/.
- Performance: 200 sequential text turns with 1,000 fictional inventory rows; p95 197.04 ms, median 119.27 ms, Python 3.14.0 on Windows AMD64. The 300 ms target passed without lowering it.
- Strict mypy passed. Final Ruff/ESLint checks and the final container health result are recorded in tasks/progress.md after their commands complete.
- Production container build succeeded, including frozen runtime dependencies, TypeScript compilation, and installation of packaged migrations.
- Independent code review found two important dialogue issues; dedicated tests reproduced both failures, then passed after fixing implicit subject-colour corrections and preventing identifying details from promoting unqualified candidates.

## Provider and physical-device evidence

The browser test uses real Chromium MediaRecorder encoding and our real HTTP/database/decision pipeline. Groq and audible playback boundaries use controlled test responses to avoid billable requests and hardware dependence. Separate backend HTTP-boundary tests verify the exact Groq endpoint, model, authentication, audio forwarding, provider errors, silence handling, and unchanged conversation state on failed transcription.

The user subsequently supplied GROQ_API_KEY in backend/.env. Compose now loads that file without exposing its contents, and the running container was recreated successfully. A real Groq whisper-large-v3 test using three synthetic WAV recordings completed the full description -> identification -> spoken confirmation transcript -> persisted pending claim flow. All three transcriptions were accurate for the scripted fictional phrases. The live test called our actual HTTP endpoints and did not mock the provider. Verification helper: scripts/verify_live_voice.py; generated samples remain gitignored under .artifacts/.

This verifies live provider integration and persisted outcomes. A physical microphone/speaker session is still separate hardware evidence; synthetic speech is not represented as a physical-device test.

AI token exports/screenshots remain external evidence not available through this coding session. AI_USAGE.md records this limitation rather than inventing counts.

## Deployment boundary

One worker, SQLite persistence, fictional data, server-only Groq credentials, staff-reviewed claims, no automatic property release. Schedule daily expiry cleanup for a long-running deployment. GitHub Actions contains the repeatable verification matrix; no remote CI or PR run is claimed.
