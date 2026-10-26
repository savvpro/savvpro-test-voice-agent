# Riverside Lost Property Implementation Plan

> For agentic workers: use the executing-plans skill in this session. Do not commit: the user owns all commits. Track observed results in progress.md and todo.md.

**Goal:** Deliver an explainable lost-property voice assistant with safe reports and staff-reviewed claims.

**Architecture:** A pure Python brain returns state and proposed effects. FastAPI validates input and persists state/effects atomically. A React client handles speech, transcripts, and safe explanations.

**Tech stack:** Python 3.14, FastAPI, Pydantic, SQLAlchemy/Alembic/SQLite, React/TypeScript/Vite, pytest/Vitest/Playwright.

**Spec:** [DESIGN.md](../DESIGN.md), approved 2026-10-26. The user authorized implementation in the existing candidate-Harris-05 checkout and will manage commits and submission.

## Global constraints

English-only; one fictional mall; bags/phones/wallets/keys; no LLM or embedding decisions; no real personal information; no private inventory facts in public output; explicit confirmation; pending staff review; one worker; the limits and thresholds in DESIGN.md and gates in CONSTRAINTS.md apply to every task.

## Review focus

- A correction combined with yes must change the search rather than confirm outdated facts (tasks 2/4).
- A lost response retried after a version change must replay safely rather than duplicate an outcome (task 3).
- A private fact that differs by one identifying token must not become a hint in trace/error/DOM output (tasks 4/5).
- An old microphone callback after restart/unmount must never submit a turn to the new session (task 6).
- Expiry/deletion must erase conversation ledgers without losing confirmed cases before their own retention boundary (task 7).

## Goal and governing documents

Deliver the complete assessment: a usable voice-and-text lost-property assistant with a deterministic Python brain, a React interface, safe persisted outcomes, reproducible checks, and genuine AI-usage evidence.

Read ../TASK.md, ../DESIGN.md, and ../CONSTRAINTS.md. Tasks are tracked in [todo.md](todo.md). This document is the canonical delivery roadmap; do not keep a second divergent task list elsewhere.

## Dependency sequence

Contract and fixtures -> pure brain -> transactional text API -> caller UI -> report/claim journeys -> real speech -> release verification.

Each slice carries tests, validation, and documentation relevant to its behaviour. The final hardening slice broadens verification; it is not the first time security or testing is implemented.

## Slice 1: Runnable text foundation

**Outcome:** A typed caller message reaches a tested Python conversation engine and receives a clarification question.

**Work:** Create minimal Python and TypeScript projects, application factory/lifespan, public turn types, a greeting/category-clarification path, frontend text input/transcript, and initial quality scripts. Resolve and lock dependencies after checking Python 3.14 support. Add .gitignore and placeholder-only environment documentation before creating local settings.

**Acceptance:** One real text turn completes through the UI; malformed text is rejected; unknown categories produce clarification; initial lint, strict types, tests, and build pass.

**Likely modules:** backend pyproject/main/domain types/dialogue/API schemas; frontend app/conversation/API client; initial tests/configs. Split this foundation into backend and frontend implementation tasks, with the API contract fixed before connecting them.

**Verification:** focused pytest and Vitest tests, backend lint/type checks, frontend lint/type checks/build, and a browser smoke check. Add an initial CI job with exactly the checks that exist.

## Slice 2: Explainable public-field matching

**Outcome:** The caller's description retrieves appropriate fictional candidates and produces a useful next question.

**Work:** Add a versioned 24-item fixture set with close neighbours and negative cases, phrase normalization, typed extraction, clock-based dates, public-field scoring, abstention, and deterministic question selection. Keep private facts out of public scorer inputs.

**Acceptance:** Synonyms, multi-field utterances, negation, uncertain fields, empty descriptions, returned items, impossible dates, ties, and insufficient evidence behave as specified. A correction invalidates previous selection. The safe trace explains rules without revealing private facts.

**Likely modules:** domain normalization, extraction, matching, question policy, fixture loader; domain scenario tests. Keep matcher and dialogue tests separate from HTTP tests.

**Verification:** parameterized golden scenarios, domain branch coverage gate, serialization tests using private-detail sentinel values. Measure retrieval outcomes on a holdout set; report errors rather than publishing an invented accuracy percentage.

## Checkpoint A: Brain behaviour review

Demonstrate three text conversations: likely match, ambiguous candidates, and no match. Review incorrect matches and clarification quality before adding claim effects. Confirm rule weights and thresholds against labeled fixtures, preserving a holdout set.

## Slice 3: Durable and isolated conversations

**Outcome:** Sessions persist across requests, remain isolated, and handle retries safely.

**Work:** Add SQLite models/migration, isolated repositories, hashed capability cookies, expiry, Origin checks, input limits, request-ID ledger, optimistic version checks, transaction rollback handling, and bounded rate limiting. Add consistent error mapping, structured redacted logs, health/readiness endpoints, and OpenAPI type generation.

**Acceptance:** Two sessions cannot access each other; identical retries reproduce the saved response; conflicting payloads and stale writes return 409 without state mutation. Empty-database migration and idempotent seeding pass. Session expiry and erasure work. No stack traces, private fields, or capabilities appear in responses/logs.

**Likely modules:** persistence models/repositories, migration, application turn service, API session/turn routes, config/security/error middleware, integration tests. Split migration, transactional turn processing, and HTTP protections into separately verifiable implementation tasks.

**Verification:** file-backed database integration tests, retry/conflict/concurrency tests, cookie/Origin/session-isolation tests, expiry tests, and OpenAPI drift check.

## Slice 4: Complete lost-report journey

**Outcome:** A caller with no convincing match can confirm a lost report and receive a durable reference.

**Work:** Add report proposal/readback, explicit confirmation precedence, atomic report insertion, receipt rendering, and safe recovery after request failure. Add the unique per-session outcome constraint before exposing confirmation.

**Acceptance:** No report is created before confirmation. “Yes, but actually it was blue” changes the search instead of saving the old report. Duplicate confirmation creates exactly one report; a failed commit never displays a receipt. The report survives a process restart.

**Likely modules:** domain dialogue/confirmation policy, application effect service, report model/repository, frontend summary/receipt, tests.

**Verification:** complete backend scenario tests, browser report/correction/retry journeys, and a restart persistence smoke test.

## Slice 5: Safe pending-claim journey

**Outcome:** A caller can supply identifying details and submit a possible-match claim for staff review.

**Work:** Add generic identifying questions, vocabulary-group checks, bounded attempts, conversation-local candidate selection, claim readback, and pending-claim receipt. Keep private fact comparison internal. Extend transactional submission without creating a second outcome path with different retry semantics.

**Acceptance:** Selecting a candidate alone is insufficient. Ambiguous or conflicting identifying evidence falls back to a lost report. Private values and per-fact results do not leak. Confirmed claim remains pending; item availability is not blocked by an anonymous claim. A simultaneous confirmation still produces one outcome.

**Likely modules:** domain identification policy/dialogue, claim model/repository, application submission service, frontend candidate cards/receipt, privacy and end-to-end tests.

**Verification:** identifying-detail boundary tests, API/DOM/log sentinel checks, competing-candidate scenarios, and browser claim journey.

## Checkpoint B: Complete typed product

Run report and claim flows against the real API, including correction, cancellation, unknown answers, retry, and expired session. Review actual screenshots at 390/768/1440 widths, keyboard navigation, and axe results. Resolve behaviour and contract problems before attaching speech.

## Slice 6: Real voice interaction

**Outcome:** On a supported browser a caller speaks, the same Python brain responds, and the browser reads the reply aloud.

**Work:** Implement small recognition/synthesis adapters, a controlled speech lifecycle, explicit microphone initiation/notice, final-transcript submission, mute/replay/stop controls, permission recovery, and cleanup on interruption/unmount. Keep interim recognition local and prevent overlapping recognition, requests, and synthesis.

**Acceptance:** Empty/silent/interim recognition causes no mutation; final recognition submits exactly once; assistant speech cannot feed back into recognition. Unsupported/denied/failed speech preserves the complete typed flow. End conversation stops all audio. A real microphone-to-spoken-reply session is observed and documented.

**Likely modules:** frontend speech adapters/hooks, conversation controls, browser type declarations, component and browser tests; voice limitations documentation.

**Verification:** adapter event tests, mocked browser failure journeys, plus a separately recorded manual real-voice test. If the environment cannot access a microphone/provider, leave that release item visibly pending rather than claiming mocked coverage proves voice works.

## Slice 7: Caller experience and safe decision inspector

**Outcome:** A clear, polished interface explains progress and decisions without obstructing the caller.

**Work:** Refine responsive layout and typography; add safe field summaries, optional inspector, retry/expiry states, confirmation readbacks, keyboard focus and live regions, and reduced-motion behaviour. This refines the functional interface built with earlier slices rather than adding a detached mockup.

**Acceptance:** All primary controls work by keyboard; tested pages/states have zero serious/critical axe findings; no overflow at the three target widths. Inspector uses only allowlisted public facts and labels heuristic scores as points, not confidence percentages.

**Likely modules:** conversation components, decision-inspector components, shared styles, accessibility/browser tests.

**Verification:** runtime screenshots, keyboard/manual checks, axe, frontend coverage, production build, initial bundle budget, and console/network inspection.

## Slice 8: Reproducible operation and submission

**Outcome:** Another engineer can clone the fork, run the app and checks, and assess the design and AI contribution.

**Work:** Complete CI jobs for every active constraint, frozen installs, migration/seed smoke tests, dependency and secret scans, container build/smoke test, expiry maintenance command/scheduling guidance, measured performance checks, and shutdown/resource cleanup verification. Review dependencies and installation scripts before allowing execution.

Preserve the supplied submission guide under docs/ASSESSMENT_SUBMISSION.md before replacing README.md with setup/run/test/demo/troubleshooting instructions. Update DESIGN.md to the implementation actually shipped. Maintain AI_USAGE.md with useful examples of assistance, mistakes/corrections, and genuine redacted token-usage exports/screenshots. Capture evidence throughout, rather than reconstructing it from memory at the end.

**Acceptance:** Fresh setup and container smoke checks pass; locks and generated API types are unchanged after verification; all blocking gates pass; measured budgets have actual results; real voice evidence is present; no fabricated usage counts or unfinished required deliverables remain.

**Verification:** full local/CI check matrix, fresh database setup, saved-outcome restart test, release diff review, and requirement-by-requirement assessment checklist. No tests currently exist, so no passing status may be claimed at planning time.

## Checkpoint C: Final review and external submission

Review correctness, privacy, maintainability, accessibility, failure recovery, and the assessment's no-AI-brain requirement. Confirm the deadline, which is absent from the repository. Prepare the PR description from final behaviour and actual test results. Submit candidate-Harris-05 from Harris-05's fork to savvpro/savvpro-test-voice-agent:main with the required title only when the implementation and evidence are complete.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Browser recognition is unavailable or fails online | Feature detection, explicit supported-browser documentation, complete typed fallback, and real voice release check |
| Lexical rules miss unusual phrasing | Versioned synonyms, uncertainty handling, useful clarification, abstention, and a labeled holdout scenario suite |
| Similarity is mistaken for ownership | Generic identifying questions, explicit confirmation, pending staff review, no automatic release |
| Private facts leak through an inspector or error | Separate public models and sentinel tests across API, DOM, errors, traces, and logs |
| Retried/concurrent turns create duplicate claims | One transactional application service, request ledger, optimistic versioning, unique outcome constraint |
| “Professional” expands into infrastructure unrelated to assessment | Bound scope to one mall, one worker, no contact data, no staff portal, and a small set of strong checks |
| Token evidence cannot be exported from this session | Document the limitation honestly and obtain genuine evidence before final submission |

## Next step

Execute the tasks below in order, without asking for repeated permission. Do not create commits or submit a PR; the user manages both.

## Executable tasks

Each task follows write tests -> observe RED -> implement -> observe GREEN -> run affected quality gates -> record evidence. Source/config setup needed to run the first failing test is allowed; do not implement behaviour before its tests. No commit step is authorized.

### Task 1: Public contracts and text foundation

Files: backend/pyproject.toml; backend/src/lost_property/domain/models.py; backend/src/lost_property/domain/dialogue.py; backend/tests/test_dialogue.py; frontend config/app foundation follows task 5.

Produces: `Conversation` (version, state, fields, attempts, selection, proposal, receipt), `FoundItem`, `Candidate`, `TurnResult`; `respond(state: Conversation, text: str, inventory: list[FoundItem], now: datetime) -> TurnResult`. Public state excludes internal candidate IDs/evidence.

- [ ] Write `test_missing_category_asks_for_item_type` and `test_cancel_has_no_effect`: a new conversation asks for the category; cancel returns state cancelled with no proposed action.
- [ ] Run `python -m pytest tests/test_dialogue.py -q`; expect missing implementation failure.
- [ ] Implement typed models and minimal deterministic greeting/clarification/cancellation.
- [ ] Run focused tests, Ruff, and strict mypy; expect no failures.

### Task 2: Extraction, ranking, and question selection

Files: domain/normalization.py, extraction.py, matching.py, dialogue.py; backend/tests/test_extraction.py, test_matching.py, test_dialogue.py; persistence/fixtures.py (fictional fixture factory only).

Consumes: task 1 models. Produces: `normalize(text: str) -> str`, `extract(text: str, now: datetime, expected: str | None = None) -> Extraction`, `rank(fields: Fields, inventory: list[FoundItem]) -> list[Candidate]`, and the complete collecting/disambiguating behaviour in `respond`.

- [ ] Write literal cases for rucksack/restaurants normalization; navy and “not blue, black”; yesterday/ambiguous/future dates; multiple facts; unknown answers; score 55 for category+colour+zone; returned/date-impossible exclusions; ties; missing description; correction invalidation; bounded question exhaustion.
- [ ] Run `python -m pytest tests/test_extraction.py tests/test_matching.py tests/test_dialogue.py -q`; observe RED for missing branches.
- [ ] Implement the exact scoring table/thresholds and open-question policy in DESIGN.md. Seed 24 fictional records with close neighbours, fixed dates in tests, and optional anchor dates for demos.
- [ ] Run tests and domain coverage; compare against independent labeled holdout cases, report mismatches rather than changing expected outcomes to fit code.

### Task 3: Transactional sessions and API

Files: persistence/models.py, database.py, application/service.py, api/schemas.py, api/routes.py, main.py, config.py; migrations/versions/0001_initial.py; tests/test_api.py, test_persistence.py.

Consumes: `respond`. Produces: `create_app(settings: Settings | None = None) -> FastAPI`; the versioned HTTP contract in DESIGN.md; `POST /turns` request fields request_id (UUID), expected_version (nonnegative integer), text (1..1000 chars); response reply, version, state, fields, candidates, trace, transcript, receipt.

- [ ] Write API tests for session greeting/cookie, missing or expired cookie, Origin rejection, invalid/large bodies, safe error envelope, absent schema readiness, cross-session isolation, duplicate request replay, request-ID payload conflict, stale version, and two concurrent requests.
- [ ] Run `python -m pytest tests/test_api.py tests/test_persistence.py -q`; observe RED.
- [ ] Implement Alembic schema, explicit SQLite transactions/FKs, hashed capability lookup, compare-and-swap, unique request ledger, same-origin protections, redacted telemetry, bounded limits, rollback errors, and migration/seed commands.
- [ ] Run integration tests, Ruff/mypy, OpenAPI export, and empty-file-database migration/seed smoke verification.

### Task 4: Confirmed reports and private claim checks

Files: domain/identification.py, dialogue.py; application/service.py; tests/test_identification.py, test_dialogue.py, test_api.py.

Consumes: tasks 1-3. Produces: `identify(details: str, candidates: list[FoundItem]) -> str | None` (internal unique item ID only); proposed action type lost_report or claim; atomic receipt `{reference, kind, status}`; final-confirmation and completed-session behaviour.

- [ ] Write complete report/claim conversations, candidate-selection-alone rejection, conflicting/ambiguous identification, “yes but actually”, repeated yes, restart confirmation, completed-session changes, failed commit without receipt, concurrent confirmation, and hidden-fact sentinel tests for output/logs.
- [ ] Run those tests and observe RED before implementing the missing paths.
- [ ] Implement generic identification questions and single-candidate evidence, confirmation precedence, unique session outcome, and transactionally returned receipt. Keep item availability unchanged by pending claims.
- [ ] Run all backend tests with coverage, strict types/lint, and restart persistence checks. Record actual domain/application coverage.

### Task 5: Typed caller interface and contract generation

Files: frontend/src/api/{schema.d.ts,client.ts}; features/conversation/{useConversation.ts,ConversationView.tsx,CaseSummary.tsx}; app/App.tsx; styles/app.css; tests/client.test.ts, conversation.test.tsx; scripts/api-types.mjs.

Consumes: generated OpenAPI `components['schemas']['SessionView']` and `TurnRequest`. Produces: `ApiClient.open/get/send/erase` and `useConversation` state with a retry object retaining the original request UUID/version/text; safe rendering of transcript, fields, candidates, trace and receipt.

- [ ] Write client tests for error mapping, identical retry identity, 409 resync, timeout and expired session; component tests for input/submit, candidate preference, confirmation/receipt, inspector disclosure, and errors.
- [ ] Run `npm test`; observe RED before implementing behaviour.
- [ ] Implement a responsive transcript-first service desk, warm neutral/green tokens, labeled text input, safe fields/candidate cards, pending receipt, and inspector. Generate schema types from backend OpenAPI; never duplicate private inventory in frontend fixtures.
- [ ] Run typecheck/lint/coverage/build and API drift checks; inspect in a real browser and run axe at 390/768/1440 widths.

### Task 6: Speech lifecycle

Files: frontend/src/speech/{recognition.ts,synthesis.ts,useSpeech.ts}; conversation voice controls; tests/speech.test.ts, useSpeech.test.tsx; tests/e2e/voice.spec.ts.

Consumes: final-transcript `onTranscript(text: string)` callback and current assistant reply. Produces: idle/listening/submitting/speaking/error state; supported-feature flags; start/stop/mute/replay/cleanup operations.

- [ ] Write tests for interim/final/duplicate events, empty result, permission/network/silence failure, unsupported recognition/synthesis, stop-before-speak, mute/replay, stale event after reset, and cleanup.
- [ ] Run `npm test -- speech`; observe RED.
- [ ] Implement typed browser adapters and generation-guarded lifecycle; explicit microphone notice and user initiation; no automatic reopening.
- [ ] Run tests and browser speech-failure journeys. Record real microphone/provider verification separately; do not count simulation as physical microphone evidence.

### Task 7: Operations and quality enforcement

Files: backend/cli.py, scripts/check_domain_coverage.py, tests/test_maintenance.py, tests/performance/test_turn_latency.py; frontend/scripts/check-bundle.mjs; Dockerfile, compose.yaml; .github/workflows/ci.yml.

Consumes: database models and complete app. Produces: seed/cleanup/export-openapi commands; coverage/bundle check scripts; frozen installs; CI lint/types/tests/contracts/browser/a11y/audit/secrets/container jobs.

- [ ] Write retention-boundary tests preserving confirmed outcomes until day 30, migration/seed idempotency tests, and 1,000-item/200-turn latency harness with independent warm-up.
- [ ] Observe RED for missing maintenance/operations behaviour.
- [ ] Implement commands and deployment image; run one worker and document the required daily cleanup schedule. Wire each CONSTRAINTS.md command to actual tooling, without lowering gates.
- [ ] Run full coverage, audits, contract and bundle gates; exercise a fresh frozen install and container when Docker is available. Record unavailable external checks accurately.

### Task 8: Whole-product verification and handoff

Files: frontend/tests/e2e/{journeys.spec.ts,accessibility.spec.ts}; README.md, DESIGN.md, AI_USAGE.md, docs/ASSESSMENT_SUBMISSION.md, docs/VERIFICATION.md, tasks/todo.md.

- [ ] Write browser journeys for report, claim, corrections, retry recovery, session isolation, and all speech failure states; observe failures before filling any missing product behaviour.
- [ ] Run the complete automated matrix and inspect screenshots/console/network output; record measured results and actual limits.
- [ ] Preserve original submission instructions, write reproducible setup/demo commands, update design to shipped behaviour, and record genuine AI evidence or its explicit pending status.
- [ ] Request a fresh whole-codebase review of uncommitted files; fix important findings with reproducing tests and rerun the affected/full checks. Leave everything uncommitted for the user, with any physical voice/usage evidence clearly pending rather than invented.
