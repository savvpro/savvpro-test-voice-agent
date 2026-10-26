# AI-assisted development disclosure

## Tools, responsibility and runtime boundary

The recorded development session used **OpenAI Codex in VS Code**, with **gpt-6.1-sol** recorded in its local session metadata. Codex assisted with architecture, Python/TypeScript implementation, deterministic grammar, state transitions, persistence, frontend/voice adapters, tests, code review, debugging and documentation. This disclosure describes that recorded session; it does not infer use of another coding tool from visual references supplied by the candidate.

The candidate selected the assessment/use case, supplied real demo conversation transcripts and UI references, directed iterations, reviewed the result and performed manual voice/device checks. On 2026-10-26 the candidate explicitly confirmed that the physical voice check and all manual device/conversation scenarios had passed. No browser/hardware/version details or audio recordings were supplied, so none are invented here.

**There is no runtime LLM.** Browser recognition/synthesis handles speech. The custom Python grammar, state machine, business validation and confirmation gate make every receptionist decision. No model SDK, model prompt, embeddings, paid speech credentials or API keys are required by the app. Using AI to develop the code is separate from using an AI model to decide appointments.

## Authentic usage evidence

The repository retains the original screenshot and earlier filtered logs unchanged, and adds a final-audit snapshot:

| Evidence | Recorded cutoff, Asia/Karachi | Scope |
| --- | --- | --- |
| [Initial filtered log](docs/evidence/codex-usage-2026-10-26.json) | 2026-10-26 17:36:04 PKT | Functional backend/frontend and the first spoken-conversation refinements; 20 project commits |
| [Strict-audit filtered log](docs/evidence/codex-usage-audit-2026-10-26.json) | 2026-10-26 19:03:04 PKT | Cumulative session usage through the first strict audit; 26 project commits |
| [Final-audit filtered log](docs/evidence/codex-usage-final-2026-10-26.json) | 2026-10-26 23:33:29 PKT | Cumulative session usage through UI iterations, conversation repairs and the final confirmation-target fix; 43 project commits through `e1676bd` |

These are **cumulative snapshots of the same primary coding session**:

| Snapshot | Input tokens | Cached input, included in input | Output tokens | Total input + output |
| --- | ---: | ---: | ---: | ---: |
| Initial | 14,840,089 | 14,599,936 | 175,628 | **15,015,717** |
| Strict audit | 30,899,359 | 30,461,952 | 270,358 | **31,169,717** |
| Final audit | 69,201,286 | 68,348,160 | 454,316 | **69,655,602** |

Do **not** add the three totals together. The final snapshot includes the earlier ones. The increase from the strict-audit snapshot to the final snapshot is **38,485,885 tokens**: 38,301,927 input and 183,958 output. Final output includes **178,317 reasoning tokens**; that subset is not added again. Cached input is also a subset rather than an additional charge/count.

The totals count repeated context processing across implementation, conversation feedback, evaluation, discussion, UI experiments, debugging, tests and documentation. They are not a count of unique words/code, a measurement of the initial implementation alone, a cost estimate or a billing statement. Most input at these cutoffs was cached. No token count was estimated from quota percentages, elapsed time or commit counts.

The logs were filtered from the primary local rollout `rollout-2026-10-26T14-48-43-01a1779c-bed1-7441-85b0-4402c7e7b9e8.jsonl`, whose metadata identifies the project directory, VS Code source and recorded model. Each evidence file retains the event timestamp, original token fields and source line. The final cited token event is **2026-10-26 18:32:55.470 UTC / 23:32:55.470 PKT**. Automatic platform approval-review sessions and work **after each cutoff** are excluded. The final documentation/consolidation commit and later conversation are outside the last snapshot. Raw conversations, unrelated account files, rate-limit payloads and credentials are not committed.

### Original quota screenshot

![Original candidate-supplied Codex usage screenshot showing 49% five-hour quota and 92% weekly quota remaining](docs/evidence/codex-usage-2026-10-26.png)

The original image is preserved without editing. It shows **49% of the five-hour quota remaining**, **92% weekly remaining**, and the labels `7:49 PM` and `Nov 2`. These are account-level quota indicators, **not project token counts**. Its SHA-256 matches the initial evidence record: `492d9f60c6c28a042bd56ba8fcc6d85204e67a5372526cc6facec99a5358726d`.

## What the AI helped deliver

| Phase | Commits at the final evidence cutoff | Delivered work |
| --- | ---: | --- |
| Initial functional product | 14 | Configuration, custom Python brain, calendar operations, persistence, transaction/retry protection, REST API, Next.js workspace, browser STT/TTS, Inspector and initial tests/docs |
| First transcript-driven refinements | 6 | Natural booking requests, availability handoff, retained references, time/date parsing, name wrappers, inline names and occupied-slot recovery |
| Usage evidence and first strict audit | 7 | Authentic evidence, operation-target/rejected-field safety, language contrasts, browser storage/retry recovery, mobile/keyboard controls, CI and audit documentation |
| Later conversation repair and initial UI refinement | 6 | Field-specific rescheduling, contextual directional answers, compound back-outs, courtesy/end distinction, themes, pinned chat and supplementary views |
| Minimal workspace and dedicated views | 9 | Collapsible navigation, first-turn suggestions, service catalog, empty/draft/saved/cancelled appointment cards, confirmation-safe action buttons and VoxDesk favicon/title |
| Final confirmation-target audit fix | 1 | Named confirmations checked against the pending operation, with nine cross-operation regressions |
| **Total at `e1676bd`** | **43** | Full commit subjects and actual timestamps are retained in the final filtered log |

The backend and frontend were already functional at initial implementation commit `bde1b5f`; the first recorded validation was 82 backend cases and six browser cases with build/type checks passing. Later changes included functional repairs, not just visual polish. Final automated validation after the last safety fix is **407 backend cases and 28 browser cases**, plus frontend clean-copy typecheck, production build, formatting, zero reported npm vulnerabilities and Python dependency integrity. [README.md](README.md#verification) records the final results and [DESIGN.md](DESIGN.md#validation-and-coverage) maps the tests to behavior.

At the candidate's request, the initial working product was grouped into component-based commits after implementation. UI experiments also remained uncommitted until the candidate approved local batching. All commits use their actual creation timestamps; no backdating, fabricated live timeline or rewritten history is claimed. The final documentation cleanup is a later commit beyond the evidence cutoff. Nothing has been pushed, submitted as a PR or deployed by the coding agent.

## Where AI-assisted work went wrong

| Observed mistake or review finding | Correction and evidence |
| --- | --- |
| A substring check for noon misread “Friday afternoon”; the first intent rules also treated “read a book” as booking. | Word boundaries and command/request contexts replaced broad matches; [test_brain.py](backend/tests/test_brain.py) retains contrasts. |
| Early phrase matching rejected ordinary booking/reschedule requests and repeatedly asked generic questions. | Added explicit request families, repair-prefix normalization, field-specific prompts and complete API/database transcript regressions in [test_spoken_conversations.py](backend/tests/test_spoken_conversations.py), [test_transcript_recovery.py](backend/tests/test_transcript_recovery.py) and [test_reschedule_dialogue.py](backend/tests/test_reschedule_dialogue.py). |
| Calendar numbers reached clock parsing; unsupported offsets could collapse to a plausible last hour. | Separate calendar-span consumption and complete clock grammar now retain valid independent fields and clarify ambiguity; [calendar](backend/tests/test_calendar_dates.py) and [language contrasts](backend/tests/test_language_contrasts.py) cover both positive and negative cases. |
| Request words were stored as names, inline names were lost after field errors, and names disappeared on occupied slots. | Anchored wrappers and independent marked-name extraction preserve the supplied name through repairs; [customer-name](backend/tests/test_customer_names.py) and [inline-name](backend/tests/test_inline_customer_names.py) suites verify persisted results. No spelling guess was introduced. |
| Context/reference loss forced callers to copy a reference that the session already knew. | Retained only verified session-local references, with explicit-reference priority and database lookup. Legacy recovery trusts the session's own assistant receipt, never a caller-quoted receipt or another session. |
| Cancellation could select an older saved booking while a new draft existed; repairing one bad field could restore another rejected value. | Separated operation scope and independently rejected fields; [test_audit_recovery.py](backend/tests/test_audit_recovery.py) verifies no unintended writes. |
| A caught rescheduling error could leave a dirty ORM object inside a transaction that still committed its clarification. | All domain validation now precedes ORM mutation. [test_workflows.py](backend/tests/test_workflows.py) catches the error inside a committing transaction and verifies the original row is unchanged. |
| The final review found “confirm booking” could authorize a pending cancellation because named confirmations shared a generic rule. | Added an explicit confirmation-target comparison. All nine pending-action/named-confirmation combinations are checked in [test_confirmation_targets.py](backend/tests/test_confirmation_targets.py); mismatches clear authorization, preserve the database and reject a subsequent stale yes. |
| Longer back-outs and polite endings fell through to generic recovery. | Whole-utterance composed control grammar now handles rejection/courtesy/end separately; [test_polite_controls.py](backend/tests/test_polite_controls.py) includes the full reported beard-booking conversation. |
| Browser storage exceptions could strand the UI, and an abandoned proposal could visually replace saved details. | Added validated pending-request recovery with memory fallback, exact-request retry and separate authoritative/proposed rendering. [recovery.spec.ts](frontend/tests/recovery.spec.ts) exercises actual lost-commit responses and fault injection. |
| Initial UI changes needed correction: a navy palette was rejected, scrolling could move the whole workspace, a mobile grid column was misplaced, and a later CSS rule hid a drawer backdrop. | Used the candidate's feedback and screenshot review to refine warm neutral themes, container scrolling, explicit grid placement and drawer behavior; browser regressions preserve navigation, draft and confirmation behavior. |
| A TypeScript narrowing error, Pytest's reserved `request` parameter, outdated UI locators and Windows/browser fixture setup mistakes interrupted checks. | Fixed each setup/implementation error and reran the relevant checks. Failed/interrupted attempts were not reported as passes; semantic timestamp assertions replaced brittle date-display text when the layout changed. |
| An npm dependency advisory affected the initial PostCSS tree. | Pinned an overriding PostCSS 8.5.31 version; the final npm audit reported zero vulnerabilities and production build/browser checks passed. This is not a general security guarantee. |

Some regressions reproduced candidate-supplied transcripts, so passing those repaired examples alone would overstate generality. Additional contrast sets vary service exclusions, operation targets, negation, field-repair order, concurrency and retry behavior. Tests were authored by the same coding agent as the implementation. Candidate manual testing is recorded separately; neither a complete natural-language guarantee nor independent recognition/accessibility/security certification is claimed.

## Final documentation and submission status

The final audit consolidated the development progress, conversation matrix and manual checklist into the three documents required by the assessment: README, DESIGN and this disclosure. The original task and authentic non-Markdown evidence remain. Stale “manual check pending” statements were replaced with the candidate's explicit completion report; CI execution and PR submission are still separate future steps.

The candidate branch remains **`candidate-TUAHASHAIKH`**. `TASK.md` is unchanged from the assessment baseline. Final work is saved locally for review; pushing the fork and opening the upstream assessment PR remain pending publication authorization.
