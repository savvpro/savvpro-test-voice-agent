# AI Usage

This is a working record, not a completed assessment evidence package. Update it alongside implementation. Never replace missing observations with estimated token counts or invented screenshots.

## Tools used

| Tool | Use so far | Model information actually available |
| --- | --- | --- |
| Codex coding assistant | Read assignment files, discuss use cases, inspect the workspace, check official documentation, draft design/constraints/roadmap | Codex; no exact parent model/version identifier is recorded here |
| Codex review subagent | Independent read-only builder review of the proposed design | `gpt-6.1-sol`, reasoning effort `medium` |
| Web research tool | Check FastAPI, SQLAlchemy, Vite, and browser speech documentation | Retrieval tool; no application inference integration |

AI tools assist development only. The shipped assistant's matching, extraction, conversation decisions, and actions must be implemented in Python rules. No runtime AI brain has been implemented or authorized by this design.

## Contribution log

### 2026-10-26: Scoping and planning

- Compared phone-assistant use cases with the user; the user selected a realistic shopping-mall lost-property desk.
- Discussed semantic retrieval. Selected explicit synonyms and weighted matching to keep the decision-making code clear and assessable.
- Drafted DESIGN.md, CONSTRAINTS.md, tasks/plan.md, tasks/todo.md, and repository working rules.
- Proposed a public/private field boundary, staff-reviewed claims, confirmation and retry safety, session isolation, and real-browser voice verification.
- The independent builder reviewer reported no important unanswered questions or material implementation contradictions.

## Corrections and limitations

- The initial matching scores and thresholds are unmeasured proposals. They must be tested against labeled fictional scenarios; they are not probabilities or established accuracy results.
- Browser speech availability and online processing limitations were checked against MDN. A typed fallback is planned, but it does not substitute for observing a real voice session before submission.
- No application code, installed dependencies, test results, or runtime failures exist at this planning stage. Record concrete implementation mistakes and corrections when they occur rather than inventing examples to fill this section.

## Token usage and evidence

### Implementation assistance and corrections

Codex implemented and tested the Python brain, transactional API, React interface, Groq whisper-large-v3 transcription adapter, browser recording/TTS lifecycle, database migrations, dependency locks, container packaging, and CI configuration. The user explicitly chose Groq during implementation and instructed that commits remain their responsibility; the earlier documentation commit was undone without losing files.

Concrete corrections: the first browser accessibility run caught insufficient contrast in missing-value labels; the initial 1,000-item latency test exceeded the budget, so repeated query tokenization/ranking was removed; the independent final reviewer found an implicit colour correction and an unqualified-candidate claim path, both reproduced and fixed with tests. Speech input lifecycle tests were migrated from browser-native recognition to recording/Groq tests when the user changed the provider. No coverage thresholds were lowered.

The final reviewer used gpt-6-astra with high reasoning effort. Runtime decisions still use Python rules only; Groq performs audio transcription.

Exact token totals are not available in the tool outputs inspected during this session. No total is claimed. The reviewer's token usage is also not exposed in its completion message.

Before final submission, attach a genuine usage export or screenshot for the development tools under `docs/ai-usage/`, redact credentials and personal paths where appropriate, and record the tool's actual input/output/cached/reasoning categories as provided. State which sessions each artifact covers and avoid double-counting parent and reviewer sessions.

| Session/activity | Input tokens | Output tokens | Other reported categories | Evidence |
| --- | --- | --- | --- | --- |
| Planning session | Not available yet | Not available yet | Not available yet | Pending genuine export or screenshot |
| Independent design review | Not available yet | Not available yet | Not available yet | Pending genuine export or screenshot |

Missing token evidence remains an open assessment deliverable. Do not describe this file as complete until the required evidence is attached and the actual totals are transcribed.
