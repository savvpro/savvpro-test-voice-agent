# Execution ledger — plan: tasks/plan.md

2026-10-26: User approved design/roadmap and authorized implementation. User requested that all commits be undone and all future commits be left to them.

Commit e211e60 was removed with git reset --mixed HEAD^; all six documentation files were preserved uncommitted, and HEAD is the original 1e8a7dc.

Execution: implement directly in the existing candidate-Harris-05 checkout; no commits, pushes, PR, or worktree relocation. The user expects to review and commit the changes here. Preserve this ledger because git history will not contain task checkpoints.

Pre-flight: Task 1 models/respond are consumed by tasks 2-4; API SessionView/TurnRequest are consumed by tasks 5-6 via OpenAPI generation; task 7 uses the same database models and app factory. No conflicting interfaces identified.

Task 1: in progress. No passing implementation claims yet.

Implementation checkpoint: Python 3.14 environment and locked-version candidates installed; first tests observed missing implementation. 19 initial domain tests passed, then 11 expected dialogue failures were observed and implemented. Backend reached 57 passing tests and strict mypy passed. First branch-aware application coverage is 91.02%; domain aggregate 95% gate still needs its checker and additional meaningful cases.

Frontend checkpoint: generated OpenAPI schema types, transcript-first React interface, pure API client, retry identity retention, safe case summary/inspector, speech recognition/synthesis adapters and controls implemented. 19 frontend tests passed. Production build passed (74.95 kB gzip JS at that checkpoint). React lint initially rejected synchronous connection updates and render-time adapter initialization; refactored these to external-system subscriptions in effects. Frontend lint then passed without suppression. Frontend coverage is running; no claim it meets the gate yet.

Ruling: Outcome uniqueness is per session plus search number, rather than per session forever — the approved design also allows a completed caller to start a new search; without this boundary, the second legitimate case fails. Retries remain uniquely protected within each search; regression test for two completed searches is required.

Ruling: Pin TypeScript 5.9.3 because the current API generator requires TypeScript 5.x and typescript-eslint excludes TypeScript 7. Current versions selected by unconstrained npm were incompatible; use declared compatible peers rather than --force/--legacy-peer-deps. ESLint 9 currently emits an end-of-support installation warning; assess compatible upgrade before handoff.

Environment: ordinary sandbox runs denied pip temp files, pytest/lint cache writes, and Node/Vite subprocess creation. Required runs use approved escalation. Python test dependency changed to httpx2 after inspecting the installed Starlette code's deprecation requirement. No tests or suppressions were weakened.

Still required: finish Python lint formatting and domain coverage gate; frontend coverage and broader behaviour tests; real-browser Playwright journeys/screenshots/axe; setup/retention/concurrency/failure tests; CLI and bundle helpers; reproducible locks and CI/container; README and truthful AI evidence; fresh whole-codebase review. Physical microphone/provider and genuine tool token evidence cannot be claimed from mocked tests. Do not commit or push.

2026-10-26, user steering: Finish the complete product end to end; use Groq whisper-large-v3 for STT with GROQ_API_KEY supplied by the user in project-root .env. No further design approval needed. The user said they will add the key now; do not print/read it through tools, only load it inside the running application. At last filename-only check the real .env did not yet exist. Keep all code uncommitted.

Before the Groq migration, 76 backend tests passed at 94.35% overall branch-aware coverage and the separate domain gate measured 99.77%. Frontend 29 tests passed with 95.26% statements / 81.53% branches / 98.48% functions / 98.13% lines. All 8 real Playwright journeys/layout/axe tests passed after fixing insufficient contrast on Not provided text and an ambiguous test locator. Matching 1,000 items initially failed the p95 performance budget at 340.95 ms; optimize repeated query tokenization/ranking rather than lower the 300 ms threshold.

Groq migration: raw audio POST /api/v1/transcriptions implemented with session/Origin protection, 8 MiB memory-only body cap, MIME/container validation, Groq whisper-large-v3 multipart forwarding, server-only credentials, bounded concurrency/timeouts, silent/empty transcript checks, and safe failure messages. Eight backend speech tests passed. New RecordingAdapter and speech upload client passed nine initial tests. Hook/controls switched to MediaRecorder and Groq, old native SpeechRecognition source retired, lifecycle tests migrated to preserve cancellation/permission/late-callback coverage. Full frontend suite then passed 33 tests. Fresh build/API regeneration and locking tools installation currently running. Recording requires explicit Finish recording; cancellation discards audio and aborts stale uploads. No audio files are stored by the product.

Final delivery checkpoint: 92 backend tests passed, overall coverage89.17%, domain98.73%. Frontend40 tests passed with all80% gates satisfied (branches80.23%). Nine real-browser tests passed including audio encoding -> transcription boundary -> brain -> TTS boundary -> claim. Performance200 turns/1000items p95=197.04ms passed. Container build succeeded.

Final review: fresh gpt-6-astra reviewer identified two important issues; tests test_identifying_answer_can_correct_the_item_colour_without_actually_keyword and test_identifying_fact_cannot_promote_an_unqualified_runner_up were observed RED, fixed, and included in the green92-test suite. No further important findings reported within the review window.

Ruling: Runtime dependencies remain hash-locked; development dependencies use an exact installed-version lock because the full development hash resolver did not finish within the user's explicit10-minute delivery deadline. Setup/CI were updated consistently; no numeric quality gate was lowered. Cost: development package downloads rely on version pinning and TLS rather than a hash allowlist.

User owns all commits and submission. No commits or pushes were created after the rollback. Root.env was still absent at the last filename-only check, so actual Groq and physical-device evidence must remain unclaimed. AI token screenshots/exports are external pending evidence.
