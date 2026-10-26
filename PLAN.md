# Voice Agent Implementation Plan — v2

> Planning assumption: one developer, 3 working days / about 24 hours. If the actual budget is smaller, preserve all **Must** items and reduce UI polish. All dependency names below are suggestions and must be **verified before use**.

## 1. Goal

Build a single-page, browser-based voice assistant that completes one real phone job: booking an automotive service appointment at a fictional repair shop.

The runtime pipeline is:

```text
microphone -> STT adapter -> transcript normalizer -> deterministic brain
           -> booking service -> response template -> TTS adapter -> speaker
```

The brain—intent selection, next question, validation, and actions—is Python code with no LLM or network access. Browser speech recognition may use ML, but it is an input adapter outside the brain.

## 2. Use Case

### Automotive service appointment receptionist

The assistant collects a fake customer's name and phone number, vehicle make/model/year, service, preferred date/time, and optional notes. It checks a fake calendar, offers alternatives, reads a summary, requires explicit confirmation, and returns a confirmation number.

Supported services and resource rules:

| Service | Duration | Required capacity |
|---|---:|---|
| Oil change | 30 min | 1 general bay |
| Tire rotation | 60 min | 1 lift bay |
| Brake inspection | 90 min | 1 lift bay |
| Battery check | 30 min | 1 electrical technician |
| General diagnostic | 60 min | 1 diagnostic technician |

Seed capacity: two general bays, one lift bay, one electrical technician, and one diagnostic technician. Availability requires the relevant resource to remain free for the full service duration.

This is a bounded, gradeable workflow commonly handled by phone. It demonstrates multi-turn collection, messy input, corrections, capacity-aware availability, and a saved outcome without adding account management or real shop integration.

## 3. Functional Requirements

### Core conversation

1. Create a session and greet the caller.
2. Accept text or one push-to-talk recording per turn.
3. Normalize the transcript, derive candidates, and run the precedence rules in Section 6.
4. Collect one missing field at a time while accepting multiple fields in one utterance.
5. Validate fields and ask a focused clarification for ambiguity.
6. Check duration and capacity for the requested slot.
7. If unavailable, offer the three best alternatives.
8. Read the complete summary and require an explicit confirmation.
9. Recheck availability atomically, save once, and return a confirmation number.
10. Allow help, repeat, correction, restart, call abort, and goodbye throughout the active session.

### One complete voice turn

The UI uses **push-to-talk**, not automatic listening. This is simpler to demonstrate, makes turn boundaries explicit, and avoids accidental barge-in and continuous microphone capture.

1. The user presses **Talk**; any assistant TTS is stopped, then the microphone opens.
2. The button shows `Listening…`; pressing it again ends capture. Otherwise, 1.5 seconds of detected silence ends the turn, with a hard 10-second limit. Browser limitations and exact API behavior must be verified before use.
3. The microphone closes before the transcript is submitted. No recognition runs while assistant TTS is playing, so the assistant cannot transcribe itself.
4. Empty or unusable recognition produces “I didn't catch that—please try again” and does not advance state.
5. The backend returns structured decision data and reply text.
6. The UI renders the decision first, then speaks the reply. **Talk** is re-enabled when TTS ends or is stopped.
7. After three consecutive recognition failures, voice input is paused and the UI points to text input; the session remains usable.

If microphone permission is denied or speech APIs are unavailable, show a persistent explanation and use text input. Text input calls the identical turn endpoint.

### Transcript normalization

Normalization is a pure, separately tested stage before parsing. It retains both `raw_transcript` and `normalized_transcript` and applies, in order:

1. Unicode/case/whitespace normalization; preserve apostrophes useful for names.
2. Domain phrase protection (`oil change`, vehicle models, service names).
3. Context-aware number-word conversion (`twenty twenty-one` -> `2021`; phone digit words -> digits).
4. Context-aware homophone resolution: `for/four` and `to/two` change only inside phone, year, time, or offered-slot contexts—not ordinary prose.
5. Digit-group joining for phone numbers (`five five five, 12, 34` -> `5551234` as collected so far).
6. Spelled-letter joining after cues such as “my name is spelled J A Y” or “model C R V.”
7. Lightweight token boundaries in place of missing punctuation; parsers must not depend on punctuation.

The checked-in corpus `backend/tests/fixtures/noisy_transcripts.json` will include raw text, conversational context, expected normalization, and expected extracted candidates. Minimum examples include:

- `oil change for a twenty twenty one corolla`
- `my number is five five five one too three for five six seven`
- `friday at for`
- `the second one` while alternatives are offered
- `my name is spelled s a r a`
- `honda c r v`
- `cancel the oil change i want a tire rotation`
- `yeah no make that monday morning`
- `two vehicles actually`
- partial phone groups across two turns
- an empty/noise-only transcript
- a non-English reply

### Dates and times

- The fictional shop timezone is `America/Chicago`, used for all interpretation, storage, display, and shop hours. The standard-library `zoneinfo` database determines DST; UTC is stored alongside the local value. Because shop hours are daytime, DST-gap hours are never offered. Ambiguous/out-of-hours local times are rejected rather than guessed.
- A clock is injected into parsers and the engine; tests use a fixed aware datetime.
- A weekday alone means the next occurrence strictly after today. Thus, “Friday” said on Friday means seven days later.
- “Next Monday” means Monday of the next calendar week, never the immediately upcoming Monday in the current week.
- A time without AM/PM is clarified: “at 4” prompts “4 AM or 4 PM?” It is not silently inferred from shop hours.
- `morning` means the preference window 08:00–11:59; `afternoon` means 12:00–16:59. It does not choose a slot until availability is ranked.
- Implement relative weekday/day-part rules explicitly and use `python-dateutil` only for strict calendar validation if helpful (**verify before use**). This is more code than a natural-language date library, but its small grammar is predictable and testable. A broad parser such as `dateparser` is deferred because silent locale/ambiguity heuristics are risky (**verify before use**).

### Session, retries, and command vocabulary

- `status` is lifecycle only: `active | confirmed | aborted | expired | ended`.
- `state` is the active dialogue step only: `collecting | choosing_slot | confirming`. Terminal sessions have `state = null`.
- **Abort call** means discard an unconfirmed draft and set `status=aborted` (`cancel`, `never mind`).
- **Cancel booking** means cancel an already saved appointment; it is explicitly out of scope. The assistant says it cannot do that and gives the fictional shop contact instruction.
- Sessions expire after 30 minutes of inactivity. The next request receives `410 session_expired`; drafts are discarded, confirmed bookings remain.
- Each required field gets at most three consecutive invalid/unknown attempts. Then the agent explains the limitation, marks the call `aborted`, and suggests contacting the fictional shop. Recognition failures have the separate cap described above.

### Domain-specific failure catalogue

| # | Trigger example | Deterministic handling rule | Named test |
|---:|---|---|---|
| 1 | “How much is an oil change?” | Say prices are unavailable; return to the pending question. | `test_price_question_returns_to_pending_field` |
| 2 | “Is my car ready?” | Say repair-status lookup is unsupported; return to pending question. | `test_vehicle_status_is_out_of_scope` |
| 3 | “Book my Honda and my Ford.” | Allow one vehicle per call; ask which one to book. | `test_two_vehicles_requires_one_choice` |
| 4 | “555” then “123 4567” | Append phone groups only while phone is pending; validate when complete. | `test_phone_collected_across_turns` |
| 5 | “My name is S A R A.” | Join spelled letters and preserve display capitalization. | `test_spelled_name_is_joined` |
| 6 | “Necesito…” | State English-only support, reprompt; count a field retry. | `test_non_english_reply_reprompts` |
| 7 | “The brakes squeal.” | Map symptom to `general diagnostic`, then ask for confirmation. | `test_symptom_maps_to_diagnostic_with_confirmation` |
| 8 | Change date after selecting slot | Clear selected slot and time; check availability again. | `test_date_change_invalidates_selected_slot` |
| 9 | Bare “yes” while name is pending | Do not mutate data; repeat the name question. | `test_yes_outside_boolean_question_has_no_action` |
| 10 | Slot taken before final confirmation | Atomic recheck fails; offer newly ranked alternatives. | `test_slot_race_offers_new_alternatives` |
| 11 | Browser microphone denied | Disable voice, show reason, keep text workflow active. | `test_mic_denied_shows_text_fallback` |
| 12 | “Cancel the oil change; I want tires.” | Treat as service correction, not call abort. | `test_cancel_noun_phrase_is_correction` |
| 13 | “At 4.” | Ask AM/PM and retain all other fields. | `test_ambiguous_hour_requests_meridiem` |
| 14 | “Friday” said on Friday | Resolve to the Friday seven days later. | `test_same_weekday_means_next_week` |
| 15 | Bare “2” while three slots are offered | Select alternative 2, not 2:00 or vehicle year. | `test_bare_number_selects_offered_slot` |
| 16 | Unsupported “transmission rebuild” | Offer general diagnostic and require confirmation. | `test_unsupported_service_offers_diagnostic` |
| 17 | Silence/no transcript | Reprompt without state mutation; apply recognition cap. | `test_silence_does_not_advance_state` |
| 18 | Duplicate confirmation request | Replay the first result; do not create another booking. | `test_confirmation_retry_is_idempotent` |

## 4. Non-Functional Requirements

- Python backend; React + TypeScript single-page frontend.
- No LLM SDK, inference call, or network access inside `app/conversation`.
- Fake data only; no secret is committed. Configuration comes from environment variables.
- Structured logs include conversation ID, turn ID, state, intent, and latency, but redact phone numbers and raw transcripts by default.
- The single-process in-memory repository uses a lock for session mutation and booking confirmation.
- CI must run backend formatting/linting, type checking if adopted, the no-LLM boundary test, and all backend tests. Frontend build/lint is included; frontend test suites are stretch work.
- A backend Dockerfile runs as a non-root user and exposes a health check. Local frontend instructions may remain separate to fit the budget.
- The page supports keyboard operation and a text-only path.
- Required deliverables: `README.md`, `DESIGN.md`, `AI_USAGE.md`, tests, and a pull request.

The result is a production-style assessment demo, not a production deployment: guarantees are explicitly limited to one Python process with ephemeral fake data.

## 5. Proposed Technical Design

### Frontend

- React + TypeScript + Vite (**verify before use**).
- One page with transcript, Talk/Stop button, text fallback, assistant reply, booking draft, and decision panel.
- Decision panel fields: `turn_id`, state before/after, resolved intent/action, candidate entities, accepted/rejected changes with reasons, pending field, and availability decision.
- Browser STT and `speechSynthesis` behind `SpeechToTextAdapter` and `TextToSpeechAdapter`; exact browser APIs must be **verified before use**.

### Backend

- Python + FastAPI + Pydantic + pytest (**verify before use**).
- Pure conversation package for normalization, parsing, precedence, state transition, and templates.
- Booking service for duration/capacity checks and atomic confirmation.
- Injected `Clock`, repository, and adapters for deterministic tests.

Server-side adapter boundaries keep the architecture valid if browser speech is later replaced:

```python
class SpeechToTextAdapter(Protocol):
    def transcribe(self, audio: bytes) -> str: ...

class TextToSpeechAdapter(Protocol):
    def synthesize(self, text: str) -> bytes: ...
```

The assessment path sends browser-produced text and receives reply text, so these interfaces have no concrete server implementation in the Must scope.

### Storage, concurrency, and idempotency

- Default storage is in memory. One process-wide lock protects capacity check + insert, preventing double-booking only within that process until restart. It does not protect multiple workers or machines and is not durable.
- The frontend generates a UUID `turn_id` once per user submission and reuses it for transport retries. The server caches the response by `(conversation_id, turn_id)`; an exact retry replays that response without reapplying mutations.
- Every session response contains an integer `version`. A new turn sends `expected_version`; mismatch returns `409 stale_turn`, preventing two tabs/requests from racing the same session.
- The final confirmation uses the same atomic lock and turn-id replay rule. Availability is rechecked inside the lock immediately before insert.
- SQLite transactions and a unique resource/time constraint are a stretch item; they would improve durability but still would not imply multi-service production readiness.

### Alternative-slot ranking

Generate free starts inside the booking window that fit the full service duration, then sort deterministically by:

1. Same requested date before other dates.
2. Same requested day-part before other day-parts.
3. Smallest absolute time distance from the requested instant or day-part midpoint.
4. Earlier datetime as the tie-breaker.

Return the first three unique slots. Tests freeze the clock and seed calendar so ordering is stable.

### Suggested structure

```text
backend/app/
  api/                 # routes and transport schemas
  conversation/        # pure brain: normalization, parsers, FSM, templates
  booking/             # availability, capacity, confirmation
  adapters/            # clock, repository, optional STT/TTS protocols
  main.py
backend/tests/
  fixtures/noisy_transcripts.json
frontend/src/
  components/ speech/ services/ types/
.github/workflows/ci.yml
README.md
DESIGN.md
AI_USAGE.md
```

## 6. LLM-Free Conversation Brain

### Session record

Each session stores `conversation_id`, lifecycle `status`, dialogue `state`, `version`, `last_activity_at`, `last_question` with expected answer type, draft fields, per-field retry counts, recognition-failure count, offered slots, processed turn responses, and structured decision history.

### Per-turn precedence table

Candidate extraction happens before any correction or command mutates the session. The first applicable row determines the primary action; accepted multi-field candidates may still be merged where the row permits it.

| Order | Condition after normalization and candidate extraction | Action |
|---:|---|---|
| 1 | `turn_id` already processed | Replay its stored response exactly; perform no parsing or mutation. |
| 2 | Session terminal/expired or `expected_version` stale | Return `410` or `409`; perform no mutation. |
| 3 | Empty/unusable transcript | Reprompt last question, increment recognition failure only. |
| 4 | Explicit goodbye/end-call phrase | Set `status=ended`; do not save a draft. |
| 5 | Explicit restart phrase | Clear the draft/retries/offers, keep session active, ask first field. |
| 6 | Correction construction, including `cancel/change/remove <entity>` or replacement candidates (“cancel the oil change, I want tires”) | Apply extracted replacements, invalidate dependent fields, then ask the next missing field. This outranks abort. |
| 7 | Standalone abort phrase (`cancel`, `never mind`, `forget it`) with no entity/replacement | Set `status=aborted`; do not create/cancel a booking. |
| 8 | Offered slots exist and utterance is a bare valid index/ordinal | Select that offered slot. Thus bare `2` means option 2 here, not 2:00 or year 2002. |
| 9 | Bare yes/no and `last_question` expects boolean | Convert it to that question's explicit action: service fallback acceptance, booking confirmation, or rejection. A confirmed booking is atomically rechecked/saved. |
| 10 | Bare yes/no but last question is not boolean | Make no field change; repeat the pending question. |
| 11 | Help, repeat, or summary request | Answer from templates, then repeat/retain the pending question. |
| 12 | Out-of-scope request | Give the bounded response, retain the pending question. |
| 13 | Other extracted candidates | Validate all candidates, merge accepted values, invalidate dependencies, then compute the next state/question. |
| 14 | No usable candidate for pending field | Focused reprompt; increment that field's retry counter and escalate at three. |

Extraction is context-sensitive but mutation-free: when alternatives are present, a bare integer is tagged `offered_slot_index`; when year is pending, a four-digit plausible value is tagged `vehicle_year`; when time is pending, a value with time language is tagged `time`. Ambiguous tags cause clarification instead of guessing.

### State transitions

```text
collecting -> choosing_slot -> confirming -> status=confirmed, state=null
     ^              |              |
     +--------------+--------------+  correction invalidates dependent data

any active state -> aborted / ended / expired, state=null
```

All replies are selected from reviewed templates and populated with structured values.

### API outline

```text
POST /api/conversations
POST /api/conversations/{id}/turns
  body: {turn_id, expected_version, transcript}
GET  /api/conversations/{id}
GET  /api/bookings/{confirmation_number}
GET  /health
```

The turn response contains reply text, version, state/status, candidate entities, accepted/rejected changes, action, reason code, pending field, draft, and offered slots.

### Enforcing the boundary

- `test_conversation_package_has_no_llm_imports` walks the conversation package AST and fails on a denylist of LLM SDK imports.
- `test_conversation_engine_cannot_open_network` runs conversation tests with socket creation/connect monkeypatched to fail. The pure package receives no HTTP client or speech adapter.
- CI runs both tests.
- `DESIGN.md` states that browser STT may be ML-based but only emits text; it is outside the deterministic brain and cannot decide intent, questions, or actions.

## 7. Important Edge Cases

The 18-item catalogue in Section 3 is the acceptance corpus. Additional boundary tests cover past/out-of-window dates, closed hours, invalid vehicle years, phone over/under length, duplicate HTTP delivery, expired sessions, stale versions, resource overlap for the full service duration, and redaction of phone-like strings.

No parser silently guesses an ambiguous date, time, vehicle, or service. It returns a typed ambiguity and a template-based clarification.

## 8. Implementation Phases

### Phase 0 — Evidence and skeleton (2 hours)

- Create `AI_USAGE.md` immediately and log this planning/editing session.
- Add Python/React skeletons, `.gitignore`, fake configuration, formatter/linter configuration, and CI shell.
- Create `README.md` and `DESIGN.md` headings and update them during every phase.

AI usage log row format:

| Date/time | Tool/model | Task/prompt summary | Input tokens | Output tokens | Evidence path | Accepted result | What AI got wrong / human correction |
|---|---|---|---:|---:|---|---|---|

Fill a row immediately after each material AI session; attach exported logs or screenshots under `docs/ai-evidence/` before committing. If a tool does not expose token counts, write `not exposed` rather than estimating.

### Phase 1 — Text-only vertical slice (8 hours)

- Define session/domain models, injected clock, service durations, capacity, and in-memory locked repository.
- Implement normalization corpus, parsers, precedence table, FSM, retries, expiry, templates, idempotency, and versions.
- Expose create-session and text-turn APIs.
- Write unit and API tests alongside each behavior, including the no-LLM/network boundary.
- Complete a text-only happy path before any voice work.

### Phase 2 — Simple decision UI (4 hours)

- Build the one-page text conversation.
- Show transcript, structured draft, state/status, action, reason, accepted/rejected candidates, and alternatives.
- Handle stale/expired sessions and restart.

### Phase 3 — Voice loop and fallback (4 hours)

- Add isolated browser STT/TTS adapters and push-to-talk lifecycle from Section 3.
- Stop recognition during TTS, implement silence/hard timeout behavior where supported, and handle permission/API failures.
- Manually run the noisy speech corpus; keep text as the authoritative automated path.

### Phase 4 — Hardening and required delivery (6 hours)

- Complete all named backend scenarios, API error tests, logging-redaction test, and deterministic slot-ranking tests.
- Add Dockerfile, health check, CI lint/build/test workflow, and run all checks.
- Finish README setup/run/test/demo instructions; finish DESIGN tradeoffs, diagram, LLM boundary, and limitations; audit AI_USAGE evidence/tokens.
- Scan Git changes for secrets and real data; prepare the required pull request.

### Stretch only after all Must checks pass

- SQLite persistence
- Frontend component tests
- Playwright end-to-end test
- Accent/voice selection

## 9. Test Plan

### Required automated suites

- Normalization corpus: every fixture produces the expected normalized form and candidates.
- Parser table tests: names, partial phone, vehicles, services, dates, times, day-parts, ambiguity.
- Precedence tests: every row in Section 6, especially correction-vs-abort, offered index, and contextual yes/no.
- FSM conversation tests: all 18 named catalogue scenarios in Section 3.
- Booking tests: duration/capacity overlaps, ranking, atomic recheck, replayed confirmation.
- API tests: create/turn/read, validation errors, stale version, expiry, and duplicate turn.
- Architecture tests: prohibited imports and network denial.
- Operational tests: structured log redaction and health endpoint.
- Frontend CI: lint and production build. Mic-denied behavior may be a deterministic adapter/unit check if time remains; otherwise it is a documented manual check.

### Pass/fail acceptance checks

| ID | Pass condition | Evidence |
|---|---|---|
| A1 | Text-only happy path creates exactly one booking and returns a confirmation number. | `test_complete_text_booking` |
| A2 | Duplicate confirm request returns the identical response and booking count stays one. | `test_confirmation_retry_is_idempotent` |
| A3 | Every catalogue row 1–18 returns its specified action/state. | Named tests in Section 3 |
| A4 | Capacity conflicts are rejected and alternatives follow the four ranking keys. | `test_capacity_blocks_full_duration`, `test_alternatives_rank_deterministically` |
| A5 | All noisy fixtures match expected normalized output/candidates. | `test_noisy_transcript_corpus` |
| A6 | Conversation code neither imports listed LLM SDKs nor opens sockets in tests. | Two architecture tests in Section 6 |
| A7 | Voice manual script proves mic closes before submit, stays closed during TTS, and recovers via text when permission is denied. | Checklist and screenshot in `docs/voice-smoke-test.md` |
| A8 | Decision panel displays the API's action, reason code, before/after state, changes, and pending field for a recorded demo turn. | Screenshot in README or DESIGN |
| A9 | Logs emitted by phone-input and booking tests contain no raw phone number. | `test_logs_redact_phone_numbers` |
| A10 | CI passes backend lint/tests, frontend lint/build, and architecture boundary tests from a clean checkout. | Pull-request CI status |
| A11 | Docker image builds and `/health` returns success when run. | documented smoke command/output |
| A12 | README, DESIGN, and AI_USAGE contain every brief-required topic and evidence links resolve. | submission checklist |

The submission is complete only when A1–A12 pass. Manual voice evidence is acceptable because browser microphone automation is outside the 24-hour Must scope; deterministic brain behavior remains automated.

## 10. Delivery Priorities

### Must

- Deterministic FSM and parsers with injected clock
- Capacity-aware booking, alternative selection, confirmation, corrections, and bounded retries
- Text-only vertical slice before UI/voice
- One-page decision-panel UI
- Push-to-talk voice loop plus text fallback
- Backend tests including noisy corpus, races/idempotency, and no-LLM boundary
- README, DESIGN, and AI_USAGE maintained from day one
- CI for lint, frontend build, and backend tests
- Backend Dockerfile and health endpoint
- Structured redacted logging
- Fake data and no committed secrets
- Pull request

### Stretch

- SQLite persistence
- Frontend component tests
- Playwright end-to-end tests
- Accent/voice selection

Do not start stretch work until A1–A12 pass.

---

## Change Log: Mandatory Changes

| Item | Addressed in PLAN v2 |
|---|---|
| M1 | Section 3, “One complete voice turn” |
| M2 | Section 3, “Transcript normalization” and noisy corpus |
| M3 | Section 6, numbered precedence table |
| M4 | Section 3, “Dates and times” |
| M5 | Section 2 capacity table; Section 5 ranking |
| M6 | Section 5, “Storage, concurrency, and idempotency” |
| M7 | Section 3, “Session, retries, and command vocabulary” |
| M8 | Sections 3 and 6 retry/escalation rules |
| M9 | Section 3, 18-row failure catalogue |
| M10 | Sections 8 and 10 |
| M11 | Section 8, Phase 0 and log template |
| M12 | Sections 1, 5, and 6, “Enforcing the boundary” |
| M13 | Section 9, A1–A12 pass/fail checks |

## Self-Audit

### Brief coverage

| BRIEF requirement | Where met |
|---|---|
| Pick a phone job and complete it end to end | Sections 1–3: automotive service booking through confirmed record |
| Caller speaks, system listens/decides/speaks repeatedly | Sections 1 and 3: pipeline and complete voice turn |
| Brain is own code; no LLM decisions | Sections 1, 4, and 6: pure FSM plus enforced boundary tests |
| Messy callers and changing details | Section 3 catalogue and Section 6 precedence/invalidation |
| Python backend | Sections 4–5 |
| React or Next.js frontend | Sections 4–5: React single page |
| Page lets user talk and see decisions | Sections 3, 5, and acceptance checks A7–A8 |
| STT/TTS may use any service | Browser adapters in Sections 1, 3, and 5 |
| README.md | Sections 4, 8, 9, and 10 |
| DESIGN.md with use case and brain | Sections 4, 6, 8, and 9 |
| AI_USAGE.md with tools, help, errors, tokens, logs/screenshots | Section 8 Phase 0 template/evidence rule; A12 |
| No committed secrets | Sections 4, 8, and 10 |
| Fake data only | Sections 1–2, 4, and 10 |
| Automated tests | Sections 3, 6, and 9 |
| Pull request | Sections 4, 8, and 10 |
| Production-style extra credit | Structure, CI, Dockerfile, health check, locking, idempotency, redacted logs, and explicit limits in Sections 4–6 |

### Mandatory-item gaps

All M1–M13 items are addressed in the plan. Frontend microphone behavior remains partly a manual smoke check because real browser permission/audio automation is not included in the assumed 24-hour Must scope; the mic-denied UI path should use an injectable frontend adapter if time permits.

### Assumptions

| Assumption | Effect |
|---|---|
| Time budget is 3 working days / about 24 hours because the input left `[N days / hours]` unresolved. | Scope is aggressively cut; SQLite and frontend automated suites are stretch. |
| One developer completes the work. | Hours and phase ordering assume no parallel implementation. |
| Chrome or Edge is used for the voice demo. | Browser speech support must be verified; text fallback is always available. |
| The fictional shop is in `America/Chicago`, open during daytime hours configured in fake data. | All date/time/DST rules use that timezone. |
| One backend process/worker runs the demo. | Lock-based double-book protection is process-local and ephemeral. |
| English-only recognition is acceptable for the assessment. | Non-English input is reprompted and bounded by retry policy. |
| Booking cancellation after confirmation is outside the chosen end-to-end job. | “Cancel booking” receives an explicit unsupported response; draft abort remains supported. |

### Top three remaining risks

1. Browser speech APIs vary by browser and may depend on vendor network services; mitigate with an adapter, a documented supported browser, and the always-available text path.
2. Deterministic language coverage can miss unexpected phrasing; mitigate with the noisy corpus, reason-coded clarifications, bounded retries, and incremental fixture additions.
3. In-memory single-process locking is not durable or horizontally safe; disclose the boundary clearly and keep SQLite/production storage out of Must scope rather than overstating guarantees.
