# AI assistance and evidence

**Candidate:** Farrukh Yousaf

AI assistance was used throughout this assessment. **No language model participates in runtime application decisions.** The candidate chose the vehicle-service use case, free-service constraint, English language, hands-free interaction, isolated demos, mandatory architecture refinements, and approved the interface composition.

## Tools and contribution

- **Codex:** requirements analysis; architecture discussion; Python/SQLAlchemy/FastAPI implementation; deterministic grammar and dialogue policy; tests; React/TypeScript and speech lifecycle; container/CI configuration; documentation; repository operations and verification.
- **Firecrawl Developer and web research:** inspected upstream assessment sources and official provider/framework documentation. These are development tools, not app runtime dependencies.
- **Neon CLI and installed Neon skills:** linked the candidate-supplied project, retained the existing SQLAlchemy/psycopg driver, pulled private service configuration, and verified real Postgres operations through the app. The fetched skill instructed reuse of the already installed skills/MCP plugin, so duplicate server configuration was avoided.
- **Impeccable and UI UX Pro Max skills:** established and reviewed the caller-first reception composition, accessibility controls, responsive behavior, and design documentation. The candidate explicitly selected composition B and requested UI UX Pro Max.
- **Built-in Imagegen:** generated three interface composition references. Generated dates, addresses, durations, vehicles, confidence claims, and other invented content were not adopted. The application renders actual API data as accessible React UI; no image model is called at runtime.
- **Independent skill-directed finish review:** identified undersized controls. A focused correction and recapture resolved the finding; final disposition was `ship`. A separate documenter records the shipped design system.

## Observed mistakes and corrections

1. An initial substring rule treated “afternoon” as “noon.” A regression test exposed it; a word-boundary rule now requests an exact time instead of inventing noon.
2. The first intent grammar treated the word “appointment” as a new booking during appointment selection. A regression test now verifies that “the oil change appointment” preserves the rescheduling task.
3. Initial test parameter IDs included a 5 MB binary value, producing unusably long test paths/output on Windows. Explicit short test IDs fixed the test harness.
4. A browser-artifact script used URL pathname text without decoding spaces, writing screenshots to a percent-encoded sibling path. It now uses `fileURLToPath`; evidence was recovered and recaptured in the intended workspace.
5. A first design pass used 42px controls despite the stated 44px target. The independent review caught this; select/send/appointment controls were corrected and re-reviewed.
6. Review found that confirmation could transfer across operation/appointment changes. Tests reproduced it; confirmation now requires the same operation and target as the preceding readback, and cancellation corrections select and read back the new target.
7. The candidate's live test exposed robotic local-voice preference and pauses caused by fixed-size chunks. English natural/Google voices are now preferred, a reply-voice selector is available, and chunks preserve sentence/clause boundaries where possible. A second live check is still needed.
8. A call restart could reuse the last goodbye as its opening utterance. Fresh calls now use the welcome greeting, while unfinished drafts retain their contextual prompt; a component regression test covers the ended-call case.

## Token evidence

Reported model: `gpt-6.1-sol`. These are separate per-session snapshots; no combined aggregate is claimed. The JSON files record each cutoff timestamp.

| Session | Input | Cached input (included) | Output | Total |
| --- | ---: | ---: | ---: | ---: |
| [Build/planning](docs/ai-usage/codex-token-counts.json) | 33,306,859 | 32,668,160 | 178,387 | 33,485,246 |
| [UI finish review](docs/ai-usage/reviewer-token-counts.json) | 269,514 | 232,064 | 1,803 | 271,317 |
| [Design documenter](docs/ai-usage/documenter-token-counts.json) | 436,021 | 396,928 | 9,336 | 445,357 |

Sanitized, machine-reported token-count events are in [docs/ai-usage/codex-token-counts.json](docs/ai-usage/codex-token-counts.json). The file records its cutoff timestamp and latest cumulative totals. **Do not sum cumulative event totals.** Cached input is included within input tokens; it is not added again. These counters are tool-reported usage, not a bill or unique-text measure.

The final assistant message and any work after the export cutoff are not included. Image-generation token usage is not exposed by the tool and is not estimated. Reviewer and documenter counters are exported separately. Do not add these to the build-session counter without verifying aggregation semantics; only the per-session measurements are claimed.

Reproduce an export from an available local Codex JSONL log with:

```sh
uv run python scripts/export_ai_usage.py --session /path/to/your/session.jsonl
```

The exporter includes only token metadata and reported model identifiers, excluding prompts, tool output, personal account state, and secrets. Raw session logs are not committed.

## Human validation and limitations

Automated tests validate actual Python decisions and transactions on both database dialects. Live microphone accuracy, browser voice quality, provider access, and public deployment require separate checks; their status is maintained honestly in [docs/VERIFICATION.md](docs/VERIFICATION.md). AI-generated assertions are not accepted as verification evidence.

## Black-and-gold revision assistance

The candidate requested a black-and-gold interface, SVG identity/icons, easier operation, and a fix for Your appointments. AI assistance replaced the visual tokens/styles, added hash-based appointment navigation and selected-reference actions, exposed typed entry, and updated component/browser checks. UI UX Pro Max and Impeccable informed the implementation. Fresh independent finish-review and design-documenter agents were used as required by Impeccable; the final review disposition was ship.

Observed corrections: the previous appointment link only scrolled to the existing summary and disappeared on mobile; it now opens a dedicated list. Whole-page transcript scrolling on initialization was replaced with local scroll-container movement. A font stylesheet import and overly specific test queries failed during verification and were corrected before the final successful build and 16-test run. Browser smoke timeout was increased to accommodate the hosted database connection; no speech accuracy was inferred from that test.

The token snapshots above retain their actual recorded cutoff. They predate this interface revision; fresh token metadata for this hosted continuation/review/documenter is not available in the local logs exposed to this run. No additional totals have been estimated or added.

## Test-drive playback and transcript animation revision

The candidate reported silent test-drive replies and requested streaming-style chat/transcription animation. Inspection found that UI responses only spoke while the microphone call controller was active. AI assistance separated one-shot reply playback from microphone listening, added pause/navigation generation fencing, retained the current utterance, resumed paused synthesis, exposed playback/start failures, and added Stop reply. One-shot replay now also clears the microphone-active flag. Actual response/recognition text receives bounded CSS word fades, with immediate reduced-motion and assistive-technology output. No runtime decision model or server token stream was introduced. Focused tests cover these speech guards, text preservation/corrections, and actual browser reveal/reduced-motion behavior. Token snapshots retain their earlier genuine cutoff; no extra usage totals are invented.

Human verification update (2026-10-26 21:26 PKT): the candidate confirmed that the public "What time do you close?" chip speaks without starting a call and that its text reveals progressively. This is candidate-reported device verification, separate from automated synthesis and browser checks.

Immediate appointment-update revision: the API already returned the committed active appointment snapshot, and React applied it before speech completion. AI assistance added a visible, actual-data change notice beside the conversation and on the appointments page, replaced the less-visible generic sidebar success note, and added tests proving that confirmed reschedules/cancellations update the card/list/count without reload or speech completion. Tests also preserve the original booking before confirmation and on a failed reschedule. A rapid-navigation component test exposed delayed default anchor navigation; handled clicks now prevent that duplicate navigation while retaining modified-link behavior. No backend mutation or confirmation rule changed, and token snapshots retain their genuine earlier cutoff.
