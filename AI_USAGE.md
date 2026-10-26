# AI Tool Usage

## Tools used

Antigravity and OpenAI Codex were used as coding assistants during this project.
They helped with implementation and refinement of the Python backend, API and
workflow tests, the React caller interface, debugging, and project
documentation. The project owner reviewed generated code against the plan and
ran the local checks.

No AI model is called by the running assistant to decide caller intent or
dialogue actions. Those decisions are deterministic Python rules in the
backend. The frontend calls backend endpoints for application behavior; its
optional speech controls use browser-native recognition and synthesis.

## Where assistance helped

- Building and refining backend modules, API endpoints, and tests.
- Checking the rule-based assistant against the documented state machine and
  edge cases.
- Replacing the starter frontend with a responsive call interface and
  connecting it to the backend session API.
- Updating setup, API, design, and frontend documentation.

## Corrections made during review

- An initial session deletion change removed the session from the store. The
  existing repository test established that deletion should mark it ended and
  retain it for retrieval, so the implementation was aligned with that
  contract and the full suite was rerun.
- An initial API workflow assumed the seeded next-day morning slot was
  available. The fixture intentionally fills that slot, so the test was
  corrected to use an available afternoon slot.
- The browser speech API may report a zero confidence value even when it has a
  usable transcript. The frontend omits that unusable confidence value so the
  backend can apply its default; actual low-confidence scores are still sent
  for the backend to handle.

## Token counts and logs

### Codex (user-provided snapshot)

- Session/chat: `01a1789e-7908-7630-819f-1ba74670ec5e`
- Context: 29% left (`184,237 used / 258K`)
- 1-month limit indicator:
  `███████████████████████████████████████████░░░░░`

### Antigravity (estimated by multiplying the Codex snapshot by 6)

- Context: 29% left (`1,105,422 used / 1,548,000` scaled capacity)
- 1-month limit indicator: same displayed proportion, since scaling both
  usage and limit by 6 does not change the percentage:
  `███████████████████████████████████████████░░░░░`

The Antigravity values are a 6× estimate based on the supplied Codex snapshot,
not independently measured Antigravity token usage. The month-limit graphic is
shown at its original proportion; it does not provide a numeric token count.

For future Codex CLI sessions, `/status` shows context usage and available
rate-limit information, not an exact per-project token total
([Codex guide](https://developers.openai.com/blog/mastering-codex-remote-for-engineering)).
Recorded per-session token usage is available in traces for Agents API
sessions; that applies only if work ran through that API flow, not ordinary
Codex app sessions ([OpenAI tracing guide](https://developers.openai.com/api/docs/guides/agents-api/tracing)).
