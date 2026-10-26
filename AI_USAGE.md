# AI Usage Log

This project was built with help from **Cursor Agent** (Composer). The dialog brain, tests, and backend structure were largely in place before the final pass; AI assistance was used to finish the Next.js voice UI, documentation, and small API tweaks.

## Tools used

| Tool | Purpose |
|------|---------|
| Cursor Agent | Implement frontend, docs, run tests, wire speech + API |
| Cursor Tab / inline | (If used during your session) small edits |

No LLM is used **at runtime** for booking decisions — only deterministic Python rules.

## Where AI helped

- **Frontend:** Conversation layout matching existing `globals.css`, Web Speech hook, API client, Next.js rewrite proxy.
- **Docs:** `SETUP.md`, `DESIGN.md`, env examples aligned with the codebase.
- **Backend:** Added `last_decision` to state payloads for the decision panel.

## Where AI needed correction / human review

- **Next.js 16:** Agent rules note API differences; verify `npm run build` after upgrades.
- **Speech recognition:** Browser-dependent; Safari/Firefox may need text-only fallback.
- **Boot effect:** Initial implementation risked re-starting conversations on re-render; fixed with a mount-only effect.
- **CORS vs proxy:** Prefer same-origin `/api` proxy in dev; direct `localhost:8001` requires CORS config on the backend.

## Token usage

Replace this section with your own usage from Cursor:

- **Settings → Usage** or billing export screenshots
- Approximate totals for the sessions that built this repo

Example placeholder:

| Session | Model | Tokens (approx.) |
|---------|-------|------------------|
| Voice agent completion | Composer | _add from Cursor usage_ |

## Assessment note

Per `TASK.md`, commit **no** API keys or secrets. This repo uses fake data and in-memory storage only.
