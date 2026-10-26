# AI usage

## Tools

- **Claude Code** with Claude Opus 5.5 as orchestrator; implementer and reviewer subagents ran on Sonnet and Opus.
- **superpowers skills:** brainstorming, then a written spec, then an implementation plan, then subagent-driven development: one fresh implementer per task, each followed by an independent review and fix rounds. The spec and plan are in `docs/superpowers/`.
- **ponytail:** lean-code guidance (stdlib first, no speculative abstractions, `ponytail:` comments mark deliberate shortcuts such as the global lock).

The brain itself contains no AI model: it is plain Python rules.

## How it helped

- Brainstorming settled scope (clinic booking, reschedule, cancel), speech approach (browser Web Speech API) and the list of messy cases before any code.
- Parallel worktree agents built independent parts (frontend, scheduling/DB, Docker/CI) at the same time.
- Per-task reviews with a fresh context found real bugs that tests written by the implementer had not covered.
- Boilerplate: Docker, CI, test scaffolds, docs.

## Where it went wrong

All of these were in AI-written code and were caught by AI reviewers, then fixed with regression tests.

- **Ordinal words parsed as dates:** "the second one" became the 2nd of the month.
- **Spoken times:** "3 30 pm" parsed as 6 pm; spoken-number times and spoken birth years were missed.
- **Emergency hidden by a name rule:** "i am bleeding heavily" at the name prompt was taken as the name "bleeding heavily". Fix: "I'm X" is a name only when a name is being asked for, and bleeding phrases are emergencies.
- **Unsafe confirm:** "no please don't book it" booked because "please" counted as yes.
- **Correction ignored:** "ok but make it 3:30" booked the old time; "no make it 3:30" dropped the correction. Now only a clean yes executes and corrections re-read.
- **Dialogue drift:** a new day during slot offers was ignored; choosing a time leaked into a reschedule; reschedule silently switched doctor to a GP; loops with no progress never gave up.
- **Frontend race:** hands-free mode could start two listen loops at once.
- **Logging:** per-turn logs were never emitted under uvicorn because no logging was configured.
- **Worktree base:** parallel agents branched from the wrong commit and had to be rebased.

Lesson: rules-based NLU and AI-written tests share blind spots; independent review plus adversarial phrasing found what the first test pass did not.

## Token usage

Fill in from Claude Code (`/cost`, `/usage`) and the Anthropic console usage page. Put screenshots in `docs/ai-usage/` and link them below.

| Tool / model | Role | Input tokens | Output tokens | Cache read/write | Cost | Screenshot |
|---|---|---|---|---|---|---|
| Claude Code, Opus 5.5 | Orchestrator | TBD | TBD | TBD | TBD | docs/ai-usage/TBD |
| Claude Code, Sonnet | Implementers / reviewers | TBD | TBD | TBD | TBD | docs/ai-usage/TBD |
| Claude Code, Opus (subagents) | Implementers / reviewers | TBD | TBD | TBD | TBD | docs/ai-usage/TBD |
| **Total** | | TBD | TBD | TBD | TBD | |
