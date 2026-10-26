# AI usage disclosure

## Scope and evidence

This account describes the Codex conversation available during development of
this repository. It is not a complete export of every historical interaction.
The repository initially tracked only `README.md` and `TASK.md`; implementation
files were already partly present when the visible Phase 2 review began. Their
earlier authorship/tool history cannot be reconstructed reliably from Git.

Known AI tool: **OpenAI Codex**, used as a coding/review assistant in this
conversation. Exact billing model identifiers, usage across any other sessions,
and other AI tools require confirmation from the developer's actual records.
No GPT/Claude/Gemini or other LLM is called to make reservation decisions at
runtime. Browser speech engines are recognition/synthesis facilities, separate
from the deterministic Python reservation logic.

## What Codex helped with

| Work visible in this conversation | Assistance |
| --- | --- |
| Phase 2 review/repair | Inspected the pre-existing FSM/parser, executed tests and adversarial conversations, repaired validation/rejection/corrections/terminal handling, and added regressions. Parser and regression-test subtasks used Codex agents. |
| SQLite persistence | Wrote repository/schema code, fictional inventory policy, transaction/idempotency safeguards, persistence/concurrency tests, and documentation. |
| Backend integration | Added the coordinating service, FastAPI schemas/routes, retry handling, sanitized errors, and integration tests. |
| React frontend | Built the Vite UI, API client, request-ID/session recovery, tests, local proxy, and browser integration script. |
| Browser voice | Added optional browser dictation/synthesis hooks, editable transcripts, lifecycle/deduplication handling, mocked voice tests, and documentation. |
| Final verification | Compared source with TASK.md, ran checks, inspected submission hygiene, and prepared design/testing/submission documentation. |

Codex used local filesystem/terminal tools, pytest, npm/Vite/Vitest, Testing
Library, and a headless Chromium-based browser for development and validation.
Those are development/testing tools, not additional AI decision services.
Browser API documentation was consulted for Web Speech behavior; relevant
references are linked in `frontend/README.md`. No image-generation service was
used in the visible work; UI illustrations are code/SVG and preview images are
browser screenshots.

## Mistakes, review findings, and corrections

The initial Phase 2 review found that all existing tests could pass while
`not correct` confirmed a booking, malformed times/impossible dates were
reinterpreted, invalid corrections retained stale values, and terminal sessions
could reopen. The origin of those pre-existing bugs is unknown; this disclosure
does not assume AI introduced them. Codex reproduced them with actual
conversations and added targeted regression coverage while repairing them.

A Codex-written browser check initially raced page reload: it could inspect the
old document before the new React page was ready. A later check exposed this
timing problem. The script was corrected to wait for a new document and restored
UI before continuing; subsequent browser checks passed.

Some first commands failed because the Windows sandbox blocked temporary
directories, npm downloads, or Vite subprocesses. They were rerun with approved
permissions. Failed/blocked commands were not treated as passing tests.

## Token totals and required usage evidence — incomplete

| Required detail | Verified state |
| --- | --- |
| Total input/output tokens used during development | unknown |
| Per-session/model token breakdown | **Not provided; needs confirmation from actual usage records.** |
| Token usage logs or screenshots required by TASK.md | **Not provided. This requirement remains incomplete.** |
| Other AI tools or earlier-session usage | **Not independently confirmed.** |

No arbitrary or unsupported estimate is reported as actual token usage. Test
counts, terminal output lengths, and source-code size are not token billing
records and cannot substitute for usage evidence.

Before final submission, obtain genuine token totals and logs/screenshots from
the tool/account actually used. Add sanitized evidence files to the repository,
link their real paths here, and record the date/range/model coverage and any
excluded sessions. Remove credentials, account identifiers, private prompts, and
real customer information from that evidence. Do not use application screenshots
or test logs as token-usage evidence.

Until that evidence is supplied, this file satisfies only the narrative part of
the disclosure. The assignment must not be described as fully submission-ready.