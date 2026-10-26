# Implementation milestones

1. Foundation: modular FastAPI/SQLAlchemy/SQLite backend, Next.js frontend, configuration and usage log. Accept: imports/install succeed; assessment and candidate branch preserved.
2. Brain: ordered intent rules, explicit parsing, state transitions and contextual corrections. Accept: deterministic tests, ambiguous information cannot authorize a write.
3. Booking/API: availability, transaction-safe create/reschedule/cancel, idempotency. Accept: actual API workflows, conflict/concurrency and persistence tests.
4. Voice and interface: turn-based speech, typed fallback, real decision inspector. Accept: frontend production build, accessible interaction and clear failure states.
5. Quality/submission: docs, complete test run, secret/working-tree review. Accept: reproducible commands and candid limitations; no push/PR/deployment without user approval.

## Constraints

`TASK.md` is the source of truth and must remain untouched. Preserve `candidate-TUAHASHAIKH`. Synthetic data only. No runtime LLM, keys, auth, telephone integration or infrastructure beyond the requested stack. Explicit confirmation before booking/rescheduling/cancellation. No fabricated evidence.

## Status — 2026-10-26, Asia/Karachi

Implementation milestones 1–4 and the local audit fixes are complete. Milestone 5 has passed local automated checks and includes authentic AI usage evidence. Physical voice verification and remote CI execution remain pending. **The candidate explicitly requested no submission; no push, PR or deployment was performed.**

The backend persists appointments, sessions and turn receipts. One SQLite transaction per mutating turn protects both booking changes and their reported outcome. The interface includes turn-based browser voice, typed fallback, actual decision metadata, separate saved/proposed appointment details, keyboard-selectable starts, compact mobile controls and safe retries. Reload recovery requires working tab storage; storage failures show a warning and retain same-tab retries in memory.

## Executed validation

| Check | Actual result |
| --- | --- |
| `.venv/Scripts/python -m pytest` | **398 passed** after the rescheduling and polite-control follow-up, one upstream Starlette TestClient/httpx deprecation warning; no failures. Local Python 3.13.3. |
| `npm run build` in isolated frontend copy | Passed production compilation, type validation and static-page generation; Next.js 15.5.28. Preserved the running development build. |
| `npm run typecheck` | Passed |
| `npm run format:check` | Passed for frontend source, components, tests and configuration |
| `PLAYWRIGHT_CHANNEL=msedge npm run test:e2e` (PowerShell environment equivalent) | **26 passed**, using the committed runner, an isolated production build, ports 3011/8011 and a real fixed-clock disposable backend. User servers on 3000/8000 were preserved. |
| Browser target protection | Runner refused a production build targeting a different backend port before launching test servers |
| `npm audit --audit-level=high` | **0 vulnerabilities** after PostCSS 8.5.31 override |
| `.venv/Scripts/python -m pip check` | No broken requirements |
| `git diff --check` | Passed; Git emitted its normal Windows LF/CRLF notice |
| Source/documentation credential-pattern scan | Tracked and untracked source/documentation text files scanned, no findings for private-key/OpenAI/AWS/GitHub credential patterns; this is a limited pattern check, not a security guarantee |
| Assessment preservation | `TASK.md` blob hash matches assessment baseline `1e8a7dc`; branch remains `candidate-TUAHASHAIKH` |
| GitHub Actions | Configured for Python 3.11/3.13 and Node 22; YAML/job structure and action SHA pins checked locally. Remote execution remains pending publication. Python 3.11 was not tested locally. |

Backend tests include actual state transitions, relative/spoken date/time parsing, uncertainty, corrections, service duration, opening/closing boundaries, explicit confirmations, conflicts, two independent application instances confirming concurrently, repeated request receipts, stale revisions/appointment versions, isolation, persistence after restart, UTC storage, configured business timezone, rollback after simulated commit failure, and prevention of partial rescheduling after caught validation errors.

Browser tests cover typed booking/corrections and raw trace, rescheduling/cancellation, a lost response after a real commit followed by reload/retry, storage exceptions and corrupt data, same-tab retry without storage, saved/proposed separation, network status/recovery, unreadable responses, keyboard focus and selectable slots. Responsive checks cover 360/390/768 pixels and minimum control sizes. Speech API tests cover sequencing, permission denial, replay/language selection and synchronous synthesis failure. The production frontend and backend are real; speech APIs and explicit fault scenarios are mocked. Desktop/mobile screenshots were generated and inspected. Test servers were stopped by suite teardown.

## Dedicated Studio services workspace

Replaced the services popup with a third workspace view inspired by the supplied reference: catalog rows with duration, price and Book buttons; a calculated combo saving; a conversation shortcut; and an opening-hours/timezone panel. The sidebar highlights Services and mobile navigation closes after selecting it. Catalog values come from the business API; a Book click sends a regular service-specific turn and returns to chat, so missing details and explicit confirmation remain backend-controlled. Returning through Start a conversation preserves the draft. The existing chat and Inspector remain mounted.

Two additional browser cases at 390px and 1440px verify navigation, absence of the popup, catalog data, both theme screenshots, draft preservation and booking handoff without an immediate receipt or confirmation. The production build/type validation, formatting and **26 browser tests passed**. Desktop and mobile screenshots were inspected. No backend code or dependencies changed; the latest backend result remains 398 passed from the preceding full run. No physical audio or remote CI execution is claimed. Local commits remain unpublished.

## Minimal chat layout and first-turn suggestions

The next UI iteration replaced the framed conversation with a centered, open transcript, right-aligned user messages, a pinned composer and inline receipts rendered only from a confirmed backend action. Navigation starts as an icon rail, expands to labels and opens as a drawer on phones. The Decision Inspector retains its actual fields, independent scroll area and expand/collapse behavior; its right-side toggle now includes the visible text “Decision inspector”.

Explore availability and Services & pricing are centered immediately above the message field in a fresh session. Sending a turn hides them; reload preserves that state and New session restores them. An unsent draft leaves them visible. Two browser cases verify this lifecycle and geometry at 390px and 1440px. Two earlier added cases cover independent navigation/Inspector resizing, draft preservation, mobile navigation and backdrop dismissal. Existing booking, recovery and voice-adapter checks remain intact.

The initial 22-case run exposed a test still querying the removed status-pill class; the same status assertion now targets its new position. Visual review caught a mobile grid-placement issue and a drawer backdrop style overridden by a later rule; both were corrected and regression-checked. The final production build/type validation, formatting and **24 browser tests passed**. Both palettes, expanded panels and mobile layouts were inspected in screenshots. This frontend-only work did not rerun the unchanged backend suite; its latest result remains **398 passed**. Physical audio and remote CI remain unverified.

The candidate initially kept this experiment uncommitted, then authorized focused local batches: layout `bf2b107`, browser coverage `d8ce1d2`, followed by the labeled Inspector/suggestion refinement and documentation. No push, PR or deployment was performed. Historical AI-usage snapshots exclude this work.

## UI refinement and latest spoken-conversation follow-up

At the candidate's request, UI work stayed uncommitted during visual iteration and was then saved first in three focused local commits:

| Commit | Change |
| --- | --- |
| `20f901d` | Warm neutral light/dark themes and responsive workspace styles |
| `26b9e9d` | Pinned chat and voice controls, separate Appointment view, default-collapsed Inspector with a right-side animated toggle, two remaining conversation shortcuts |
| `edc3330` | Existing browser flows updated to navigate Appointment and explicitly open the Inspector |
| `03efb44` | Reschedule request families, field-specific questions and contextual destination handling |
| `6dd832b` | Compound proposal rejection, polite endings, courtesy acknowledgements and truthful no-pending replies |

The latest transcript exposed narrow “change the timing” matching, a generic reschedule question that only asked for a date, unhandled longer back-outs and a missed polite goodbye. Added **58 backend regressions**: 29 reschedule cases and 29 control/full-conversation cases. Each initial targeted run reproduced 24 failures with five cases already passing. An initial test collection error used Pytest's reserved `request` parameter name; it was renamed before those runs. The full suite also caught a legacy-reference recovery path being cleared by the new destination question; restricting that reset to explicit action requests fixed it.

The complete supplied beard-booking conversation now retains its reference/date/name, accepts clear destination answers within the active reschedule, discards the proposed move on the longer back-out, and ends politely. The original 16:00 appointment remains unchanged. New sessions still need a reference; garbled words or reported past actions cannot start a reschedule by themselves. Every calendar write still requires a later explicit confirmation.

The UI was checked with the existing 20 browser workflows plus an isolated navigation/animation check. Both themes and mobile layouts were visually inspected; targeted text-contrast checks passed. Temporary visual checks and screenshots remain ignored artifacts, not extra committed test cases or physical voice evidence. Backend/voice behavior was preserved during the UI work. UI and subsequent backend commits use their actual creation timestamps. Publication remains on hold.

## Strict-audit remediation

The audit found safety defects beyond the reported transcripts and weak browser failure/accessibility coverage. Five focused local implementation commits address them:

| Commit | Change | Validation added |
| --- | --- | --- |
| `259149e` | Explicit cancellation targets; discard changes without cancelling stored appointments; retain every rejected field until independently repaired | 17 operation/repair cases; initial targeted run reproduced 14 failures |
| `91b64c6` | Service exclusions, complete quarter-to parsing, unsupported/negated time clarification, negated dates, bounded day offsets and request families | 49 language contrast cases; initial targeted run reproduced 39 failures |
| `6dfccb8` | Validated storage cache, recoverable storage/response errors, actual connection indicators, authoritative saved details and separate proposals | 7 browser failure/recovery cases |
| `ba9ab01` | Readable labels, larger controls, compact mobile layout, keyboard focus/slots, reply replay, language choice and synthesis-failure recovery | 7 browser interaction/accessibility cases |
| `f893f5b` | SHA-pinned CI, frontend formatting check and browser build-target/port isolation | Full 20-case browser run using committed configuration; mismatched backend target rejected |

The complete backend suite increased from 274 to **340** tests and the browser suite from 6 to **20**. The new contrast sets vary meaning and repair order rather than only copying transcript spellings. They remain coding-agent-authored checks, not an independent user study or proof of unrestricted language understanding. [CONVERSATION_TEST_MATRIX.md](CONVERSATION_TEST_MATRIX.md) maps coverage and provides a held-out manual protocol.

During verification, Windows permissions on Python-created temporary directories initially prevented Node from reading an isolated build; an ordinary workspace directory fixed that setup issue. A browser output directory initially overlapped the isolated build directory and was narrowed to `test-results/browser` before the final passing run. Neither failed setup was counted as a successful check. Documentation was consolidated after these implementation commits, with historical results retained below.

## Follow-up: real spoken-conversation feedback

The user's transcript exposed narrow booking phrases, filler words included in names, generic recovery after a misheard booking request, and loss of a known reference during rescheduling. Added 35 regression cases, including the complete reported conversation, directional time changes, status questions, legacy session-reference recovery, session isolation, explicit-reference priority, negation, draft cancellation safety, and protection against restoring rejected dates/times. The initial targeted suite reproduced 24 failures before the fixes; the final full backend run passed all 117 cases. Frontend typecheck passed with the extended session contract.

The follow-up retains a session's last verified reference, supports ordinary booking requests, asks targeted clarification after unclear availability follow-ups, cleans bounded name fillers, and selects brief topic-specific business replies. All booking writes still require explicit confirmation. No LLM or fuzzy transcription-to-action guess was introduced.

At this historical follow-up, the earlier production build and six browser-test results predated the changes. The user had running app servers on ports 3000/8000; those were preserved, and the browser suite was not rerun against its conflicting default ports. The spoken-conversation cases exercised the actual HTTP API and database with an isolated fixed clock. Frontend executable behavior was unchanged; its session type gained the remembered reference field. The later audit run above supersedes these historical validation counts.

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
- Review the authentic screenshot and filtered local-session token counters in [AI_USAGE.md](../AI_USAGE.md). The original 17:36:04 PKT snapshot covers 20 project commits; a separate 19:03:04 PKT snapshot covers 26 commits and the intervening review/fixes. Neither includes its own later documentation commit. No quota percentage was converted into token counts.
- Complete a held-out conversation run using the test matrix and record actual outcomes; this has not been independently performed.
- Remote CI and the submission PR remain pending. A read-only check found no assessment submission PR for `TUAHASHAIKH:candidate-TUAHASHAIKH`. The candidate then explicitly requested **“dont submit yet”**. Local commits are authorized; publication remains on hold.
- The intentionally small English grammar and local-demo limitations are documented in README/DESIGN. The non-failing Starlette/httpx warning is from installed upstream test-client integration.

## Commit organization

At the user's request, the completed implementation is grouped into focused commits for the project setup, domain/configuration, persistence, language parser, state machine, booking operations, REST API, backend tests, frontend scaffold, typed API client, browser voice adapter, workspace interface, browser tests, and documentation. These commits are assembled after development, with their actual creation timestamps; they are not a chronological record of the original implementation sessions.
