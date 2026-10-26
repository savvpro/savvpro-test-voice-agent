# AI Usage

AI tools may help create the submission, but no AI model runs inside the application or makes conversation decisions.

## Usage log

| Date/time | Tool/model | Task/prompt summary | Input tokens | Output tokens | Evidence path | Accepted result | What AI got wrong / human correction |
|---|---|---|---:|---:|---|---|---|
| 2026-10-26 | OpenAI Codex (model not exposed) | Read TASK.md and produce PLAN v1 | not exposed | not exposed | User/Codex conversation export or screenshot to add before submission | Initial requirements and architecture | Initial plan lacked precise voice lifecycle, precedence, capacity, concurrency bounds, and pass/fail evidence. |
| 2026-10-26 | OpenAI Codex (model not exposed) | Rewrite PLAN v1 from reviewer checklist and implement the repository | not exposed | not exposed | User/Codex conversation export or screenshot to add before submission | PLAN v2, backend, frontend, tests, docs, CI/Docker | Time budget was absent; Codex explicitly assumed 24 hours. Human must verify browser voice behavior and dependency versions. |

## How to maintain this file

Add a row immediately after every material AI session. Use actual token totals if the tool exposes them; otherwise write `not exposed` rather than estimating. Before submission, export the relevant tool logs or screenshots into `docs/ai-evidence/`, update each evidence path, and record rejected suggestions as well as accepted ones.

## Human verification checklist

- Review every generated source file and test assertion.
- Run backend lint/tests and frontend lint/build from a clean environment.
- Verify the supported browser voice loop manually.
- Confirm no real customer details, credentials, `.env`, or generated evidence containing secrets is committed.
- Replace placeholder evidence descriptions above with real paths before opening the pull request.

