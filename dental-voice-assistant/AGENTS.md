# AGENTS.md: rules for AI coding agents

## Hard rules
1. The brain is rule-based. NO LLM or LLM SDK anywhere in `ai-tool/`. Whisper = STT only.
2. No secrets in git. Only `.env.example`. Fake data only.
3. Dependency direction: frontend -> backend -> ai-tool. ai-tool imports no web or DB framework.
4. All reply text lives in `ai-tool/src/voice_agent/brain/responses.py`.
5. Inject `Clock`; never call `datetime.now()` inside the brain.
6. Do not log PII (names, phone numbers). Mask phones.
7. Every feature ships with tests. Do not mark a task done with failing tests.

## Commands
- Setup:  `make setup`
- Dev:    `make dev`          (docker compose up)
- Test:   `make test`         (ai-tool, backend, frontend unit)
- E2E:    `make e2e`
- Lint:   `make lint`
- ai-tool tests:  `cd ai-tool && pytest`
- backend tests:  `cd backend && pytest`
- frontend tests: `cd frontend && npm test -- --run`

## Style
- Python 3.11+, ruff (line length 100), mypy strict on ai-tool.
- TypeScript strict. Function components and hooks. No `any` unless commented.
- Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`.

## Done means
Lint clean, types clean, tests green, docs updated if behaviour changed.