# Neon setup and configuration changes

## Requested skill and existing setup

Fetched and followed https://neon.com/.well-known/agent-skills/neon/SKILL.md, alongside the installed `neon-postgres` skill. Reused the established Python ORM/driver and the supplied project; no replacement project, authentication provider, Data API, Functions, Object Storage, Realtime, or AI Gateway was added.

The installed, enabled `neon-postgres` Codex plugin contains both agent skills and its OAuth MCP server manifest (`https://mcp.neon.tech/mcp`). The fetched skill explicitly says not to also run `neon mcp` and `neon skills` for an agent already using the plugin. No duplicate project MCP/skill configuration was written. Existing non-Neon MCP registrations remain present. MCP invocation was not exercised in the current chat; authenticated CLI access and database connectivity were verified instead.

## Changes made

1. Installed Neon CLI 8.11.4 globally with `npm i -g neon@latest`.
2. Requested `neon init` installed the Neon plugin for Codex, VS Code, and Claude Code. Optional GitHub Copilot CLI plugin installation failed, stopping that initial command. Retried with `--no-agent-setup` to reuse the successful installations.
3. Completed browser OAuth login and reused that local credential profile. Credentials remain outside the repository.
4. Linked the supplied org/project/production branch in ignored `.neon`. The CLI added `.neon` to `.gitignore`.
5. Created `neon.ts` and its provisioning-only npm dependencies/lockfile. Existing production policy is preserved; the plan and deploy both reported no changes. Postgres is the only utilized service.
6. Pulled `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, and `NEON_BRANCH` into ignored `.env.local`. No values are committed or included in this report.
7. Updated FastAPI settings to load `.env.local` and `.env`, with process environment variables taking precedence. Kept SQLAlchemy 2.0 and psycopg 3; the application uses the pooled TLS connection.
8. Added root npm build/check/test scripts, preserving the generated dependencies. `npm run build` performs the locked frontend install and production build.
9. Created ignored `.env.render` with the two required Render variables: `DATABASE_URL` and `SECURE_COOKIES=true`. Import this private file through Render's environment UI; it is not a deployment artifact to publish.
10. Added settings regression tests and `scripts/verify_database.py` for a real API/database workflow verification.

## Command evidence

`neon deploy`:

```text
Applying to branch production
No changes — branch production already matches the policy.
Utilized services: Postgres
Pulled 3 Neon variables into .env.local
Postgres DATABASE_URL, DATABASE_URL_UNPOOLED
Branch NEON_BRANCH
```

`npm run build`:

```text
tsc -b && vite build
1935 modules transformed.
dist/index.html
dist/assets/index-DEeIs_Tr.css
dist/assets/index-CT-BgjtW.js
built in 549ms
```

With FastAPI running against the pulled database, `uv run python -m scripts.verify_database`:

```text
PASS: running API uses the configured Neon Postgres; two isolated bays seeded.
PASS: rescheduling persisted through the real API.
PASS: 60-minute booking has two contiguous segments on one bay in Neon.
PASS: cancellation releases capacity; a fresh API read recovers the committed booking.
PASS: isolated demo reset restores initial fixtures on Neon.
```

All workflow data is synthetic. Verification used the real Neon database and an actual HTTP client, not provider mocks. The same verification subsequently passed against the hosted API at https://savvpro-test-voice-agent.onrender.com. A real browser smoke also passed there for booking, alternatives, selection, rescheduling, cancellation, reset, and desktop/mobile rendering. Deploy the latest candidate commit for all final refinements.
