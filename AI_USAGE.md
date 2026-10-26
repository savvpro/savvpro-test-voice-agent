# AI-assisted development disclosure

VoxDesk was implemented with OpenAI Codex in the candidate's local workspace. Codex assisted with architecture, Python/TypeScript implementation, tests, debugging, dependency review, interface review, and documentation. No other AI coding tool was used by this agent. The runtime application makes no LLM calls and needs no LLM credentials. Browser speech recognition and synthesis handle audio only; Python rules determine every action.

## Authentic usage evidence — candidate action required

This session does not expose a reliable token-usage meter or downloadable usage log to the coding agent. **Actual token counts: unavailable; to be filled from the candidate's authentic Codex usage records.** No counts or screenshots have been fabricated. Attach real screenshots/logs before submitting.

| Date (Asia/Karachi) | Tool / model shown in UI | Task / prompt summary | Input tokens | Output tokens | Total tokens | Evidence file or link |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-26 | OpenAI Codex / record displayed model | Foundation, deterministic engine, booking API, frontend, tests and docs | Pending authentic data | Pending authentic data | Pending authentic data | Candidate to attach |

Record usage after each working session. Keep screenshots free of secrets and real personal data. Do not estimate numbers as actual usage.

## Review and corrections

Observed issues from this implementation session:

| AI-assisted mistake / review finding | How it was corrected and verified |
| --- | --- |
| The first time parser used a substring check for noon, accidentally assigning 12:00 to “Friday afternoon”. | The entity test failed. Word boundaries replaced the substring check; the fixed-clock parser tests passed. |
| Initial intent rules treated the noun in “read a book” as a booking command. | Tightened creation patterns to command/request contexts and retained a regression case. |
| After adding “yesterday” extraction, the engine asked for a time before rejecting the past date. | A workflow test failed; known dates are now validated before asking for additional details. |
| A UI refactor lost TypeScript's null narrowing for the conversation object. | The production build failed, optional chaining was corrected, and the subsequent build/typecheck passed. |
| The first browser-test server command used forward slashes in a Windows command-shell executable path. | Corrected the platform-specific path; the servers and browser suite launched successfully. |
| An unscoped browser test found both the app alert and Next.js's route-announcer alert. | Scoped the assertion to the conversation region. This was a test-locator issue; the permission error was already rendered. |
| Screenshot review showed that scrollIntoView could scroll the entire workspace when new messages arrived. | Changed scrolling to the message container and reran connected browser flows/screenshots. |
| Review found that rescheduling assigned ORM fields before validating the customer name; a caught domain error could leave a dirty object. | All validation now precedes mutation. A regression test catches the error inside a committing transaction and verifies the original appointment is unchanged. |
| The initial Next.js dependency tree included a PostCSS version flagged by npm audit. | Added a patched PostCSS 8.5.31 override. The final audit reported zero vulnerabilities; the build and browser flows were revalidated. |
| Real user testing exposed narrow phrase matching (“make a booking”), filler captured in a name (“And John”), generic recovery after unclear speech, and reference memory lost between workflows. The first automated suite did not cover this spoken conversation. | Added the reported conversation and ordinary-language/safety regressions: the initial new suite reproduced 24 failures. Expanded deterministic grammar, retained verified session references and related workflow details, added targeted status/reference recovery, cleaned name fillers, and guarded explicit confirmation and rejected fields. Current executed results are recorded in the progress log. |
| A second real transcript exposed silently ignored malformed approximate times, details discarded after availability, unhandled repair prefixes, space-separated hour/minute tokens, and “new booking” phrasing. | Added another complete API/database conversation regression and related safety cases. The initial targeted run reproduced 25 failures (5 cases already passed). Shared repair normalization and booking grammar, validated explicit time claims, retained/refreshed availability follow-up details, and bounded affirmative-action confirmation corrected the faults. The final full backend suite passed 156 tests. Browser recognition/audio quality was not claimed to be fixed or physically reverified. |

The third transcript exposed missing calendar-date formats and date numbers reaching the clock-time parser. The initial targeted run reproduced 35 failures out of 37 cases. A separate deterministic calendar grammar now consumes valid and invalid date spans before time extraction, with named-month/ordinal and year-first numeric support. Additional tests caught a partial word-ordinal match (“thirty third” becoming the third day); the grammar now consumes out-of-range day words and rejects them through calendar validation. The final full backend suite passed 202 tests. No physical speech recognition quality was inferred from these text/API regressions.

Sandbox socket and Node write restrictions required approved command retries. Those environment errors were not reported as successful installs/checks. No test results, token counts, screenshots or physical voice verification were invented.

Executed checks and remaining verification limits are documented in [docs/PROGRESS.md](docs/PROGRESS.md). Browser UI screenshots under ignored test artifacts demonstrate UI rendering only, not AI token usage or physical speech verification.
