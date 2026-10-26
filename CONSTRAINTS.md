# Engineering Constraints

Status: user-approved quality contract for the initial implementation, 2026-10-26. Activation of tooling is tracked below and in tasks/todo.md.

There is no application or test suite yet. Commands below are the planned enforcement mechanisms, not checks that currently pass. Activate each row with the slice named below, and record actual baselines before calling a measured target satisfied. Do not silently weaken this file to make a change pass.

## Always required

- The decision-making brain is our Python code. No LLM calls, embedding services, or generative decision dependencies.
- Fictional records only; no real names, contacts, credentials, or device identifiers.
- No secrets committed, including in screenshots, usage exports, fixtures, or logs.
- Private inventory facts stay out of public APIs, traces, browser assets, and telemetry.
- No skipped tests, removed assertions, blanket suppressions, empty error handlers, or unimplemented stubs used to conceal a failure. Any justified exception must be explicit and reviewed.
- A claim requires explicit confirmation and remains pending staff review.
- Database effects are transactional and idempotent; concurrent sessions cannot read or mutate each other's data.
- Do not represent a mocked speech test, synthetic performance measurement, or generated token estimate as a real observation.

## Planned blocking checks

Commands run from backend/ or frontend/ as indicated. Add these exact script names/configurations when their owning slice lands; keep this file and CI in sync.

| Dimension | Required result and reason | Command | Activation |
| --- | --- | --- | --- |
| Python formatting/lint | Zero findings; keep changes consistent and reviewable | backend: `python -m ruff check .` and `python -m ruff format --check .` | First backend slice |
| Python types | Zero errors under strict project configuration | backend: `python -m mypy src` | First backend slice |
| Backend tests | All tests pass; >=85% branch-aware coverage over application source and >=95% over domain modules; the brain deserves the higher bar | backend: `python -m pytest --cov=lost_property --cov-branch --cov-report=xml --cov-report=json --cov-fail-under=85` then `python scripts/check_domain_coverage.py --minimum 95` | First backend slice; script reads the existing coverage JSON, no second suite run |
| TypeScript/lint | Strict types and zero lint errors | frontend: `npm run typecheck` and `npm run lint` | First frontend slice |
| Frontend tests | All tests pass; >=80% lines, functions, branches, and statements in feature/API/speech source | frontend: `npm run test:coverage` | First frontend slice |
| Build | Production bundle builds without errors | frontend: `npm run build` | First frontend slice |
| API contract | No difference after regenerating committed OpenAPI types | frontend: `npm run api:check` | First integrated API slice |
| Browser journeys | Required report, claim, correction, retry, isolation, and speech-failure journeys pass | frontend: `npm run test:e2e` | First integrated caller flow |
| Accessibility | Zero serious or critical axe-core violations on tested states; keyboard checks also required | frontend: `npm run test:a11y` | First integrated caller flow |
| Frontend dependency risk | No unmitigated high/critical findings, including build/test dependencies | frontend: `npm audit --audit-level=high` | First frontend lockfile; task end and CI |
| Python dependency risk | No unmitigated high/critical findings; unknown severity requires explicit triage | backend: `python -m pip_audit -r requirements.lock` | First backend lockfile; task end and CI; pip-audit fails on findings, any exception requires documented triage |
| Secrets | No detected secret; redact output | CI: `gitleaks git --redact --no-banner` | First CI slice; full history for submission |

The domain coverage helper only selects the domain files from coverage.py's existing JSON and checks branch-aware totals; it must not alter coverage data or exclude inconvenient modules. When a dependency tool does not provide severity reliably, treat its failure as blocking pending review, not as a clean scan.

## Measured release budgets

These are proposed targets to verify after implementation, not current baselines:

- Frontend initial JavaScript <=200 KiB gzip, checked with `npm run check:bundle`; leaves room for a small caller UI without shipping unnecessary frameworks.
- Backend turn p95 <=300 ms over 200 sequential text turns with 1,000 fictional inventory rows on a documented machine, excluding speech and network time, checked with `python -m pytest tests/performance -m performance`. Include warm-up separately and report actual hardware and results. Do not enforce the wall-clock target on noisy shared CI runners; correctness remains blocking there and performance is a measured release gate.
- Browser layouts fit at 390, 768, and 1440 CSS pixels with no horizontal page overflow; verify in Playwright and inspect screenshots.
- A real supported-browser voice session passes before submission. Record browser version, date, permission result, and any limitations; do not fabricate microphone evidence.

## Execution cadence

- During an edit: focused tests and the affected formatter/type checker.
- At slice completion: related coverage checks, build when frontend changed, public-field/privacy checks, and a diff review. Aim for roughly 90 seconds; report measured slow checks rather than omitting them.
- In CI and before submission: full tests, contracts, browser journeys, accessibility, audits, secret scan, migration/seed smoke checks, and container smoke test.
- Keep verified changes on candidate-Harris-05 without committing or pushing; the user explicitly manages commits and submission.

## Exceptions and baselines

No exceptions or measured baselines have been approved or recorded. Add any proposed exception with scope, reason, owner, and expiry; do not turn a failing gate into a warning without review. More stringent numbers can be adopted when evidence supports them.
