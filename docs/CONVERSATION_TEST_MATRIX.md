# Conversation validation matrix

The deterministic brain needs more than examples that mirror reported transcripts. These contrast sets vary intent, exclusions, target scope and repair order. They were authored by the same coding agent; independent human evaluation is still pending. Current executed totals are **398 backend tests and 24 browser tests**; see [PROGRESS.md](PROGRESS.md) for environments and limits.

| Family | Contrasts / failure cases | Automated evidence |
| --- | --- | --- |
| Operation target | Discard a reschedule vs cancel a confirmed appointment; cancel a new draft while an older booking exists; ambiguous “cancel it”; explicit reference priority | [test_audit_recovery.py](../backend/tests/test_audit_recovery.py) |
| Independent field repair | Invalid date and time, repaired in both orders; intervening service error; stale original values must not return | [test_audit_recovery.py](../backend/tests/test_audit_recovery.py) |
| Service meaning | Haircut plus beard vs haircut without beard; unsupported positive vs excluded service; alternatives and contradictions | [test_language_contrasts.py](../backend/tests/test_language_contrasts.py) |
| Complete time meaning | Quarter-to vs quarter-past; noon/midnight boundary; unsupported offsets/ranges; negated time must not become a positive hour | [test_language_contrasts.py](../backend/tests/test_language_contrasts.py) |
| Date meaning | Negated dates, bounded day offsets, calendar values protected from clock extraction | [test_language_contrasts.py](../backend/tests/test_language_contrasts.py), [test_transcript_recovery.py](../backend/tests/test_transcript_recovery.py) |
| Request families | Fit/squeeze me in, I need, I'd like, please book and can I get, each with single/combined services | [test_language_contrasts.py](../backend/tests/test_language_contrasts.py) |
| Reschedule dialogue | Time/date-only requests, open date-or-time questions, contextual directional answers, bounded command repairs and negation | [test_reschedule_dialogue.py](../backend/tests/test_reschedule_dialogue.py) |
| Natural controls | Compound back-outs, courtesy vs closing, repeated rejection with no pending request, unchanged calendar and the complete beard-booking transcript | [test_polite_controls.py](../backend/tests/test_polite_controls.py) |
| Reported conversations | Availability handoff, repair prefixes, retained references, inline names, invalid dates and occupied slots | [test_spoken_conversations.py](../backend/tests/test_spoken_conversations.py), [test_transcript_recovery.py](../backend/tests/test_transcript_recovery.py), [test_customer_names.py](../backend/tests/test_customer_names.py) |
| Browser failure recovery | Blocked reads/writes/removals, malformed cached request, lost committed response without storage, unreadable response, offline/retry indicators | [recovery.spec.ts](../frontend/tests/recovery.spec.ts) |
| Authoritative appointment | Appointment view keeps saved fields separate from a proposed move; abandoning a proposal preserves saved details | [recovery.spec.ts](../frontend/tests/recovery.spec.ts) |
| Workspace and first-turn suggestions | Navigation and Inspector resize independently; drafts survive navigation; mobile drawer dismisses; two centered suggestions disappear after a turn, stay hidden on reload and return for New session | [workspace.spec.ts](../frontend/tests/workspace.spec.ts) |
| Interaction and speech adapter | Keyboard focus, keyboard slot choice with the Inspector closed, 360/390/768px layouts, touch heights, replay/language and synthesis failure | [accessibility.spec.ts](../frontend/tests/accessibility.spec.ts) |

These cases complement existing API, persistence, concurrency, idempotency and calendar-boundary tests. Passing them does not prove arbitrary English, transcription accuracy, complete accessibility compliance or production security.

## Held-out manual protocol

Use a fresh local demo database or record the original references so existing synthetic bookings are distinguishable. Use fictional names only. Record the business date/time, browser and actual utterances; avoid the automated suite's fixed clock unless intentionally reproducing a test.

1. Have another person write at least ten requests before reading the parser patterns. Include booking, availability-to-booking, a service exclusion, an interrupted request, a name correction, rescheduling, draft rejection and cancellation. Keep these requests unchanged for the first run.
2. Run each as typed text first. Record extracted details, clarification quality, proposal, actual database outcome/reference and whether confirmation was required. A safe clarification is acceptable for unsupported wording; a silent wrong interpretation or unauthorized write is a failure.
3. Repeat through a physical microphone. Save the actual recognition transcript alongside what was spoken. Distinguish recognition errors from parser behavior; do not edit the transcript before recording the outcome.
4. Include a lost connection and blocked browser storage. Verify warnings, exact-request retry and whether reload recovery is available. Never assume an uncertain confirmation failed; retrieve or retry its original request.
5. Verify a discarded reschedule leaves its saved appointment unchanged, and an abandoned new draft does not cancel an older booking. Check saved vs proposed UI details directly.
6. Record successes, safe clarifications and failures separately. For a defect, add a regression and rerun related contrast cases, then use a newly written held-out request to avoid reporting the repaired example as independent validation.

Record physical audio results in [DEMO_CHECKLIST.md](DEMO_CHECKLIST.md). No held-out human run or physical audio verification is claimed in this repository yet.
