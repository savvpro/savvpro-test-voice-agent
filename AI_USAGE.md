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

Sandbox socket and Node write restrictions required approved command retries. Those environment errors were not reported as successful installs/checks. No test results, token counts, screenshots or physical voice verification were invented.

Executed checks and remaining verification limits are documented in [docs/PROGRESS.md](docs/PROGRESS.md). Browser UI screenshots under ignored test artifacts demonstrate UI rendering only, not AI token usage or physical speech verification.
