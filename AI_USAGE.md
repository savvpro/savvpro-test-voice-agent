# AI usage record

## Tools

- OpenAI Codex desktop: brainstorming, workflow research, architecture, implementation and tests. No LLM is used for runtime decisions.
- Built-in Image Generation: one full desktop UI concept guiding ivory/forest colors, serif headings, conversation workspace, booking details and inspector.
- Web search: restaurant-owned sites linked in DESIGN.md, used for workflow inspiration.

## Corrections to AI suggestions

- The initial proposal included Whisper/Azure, SQLAlchemy/Alembic and Tailwind. The runnable first version instead uses browser speech, SQLite and native CSS. This scope change is documented rather than claiming integrations exist.
- The Windows Python alias was inaccessible; a uv-managed environment supplied the runtime.
- Port 8000 was occupied. Backend and frontend proxy use 8011.
- Local uv cache access required an explicit sandbox approval retry.
- The extended tests caught an error-handler ordering bug: a synchronous microphone permission failure was being cleared immediately after recognition started. State is now initialized before starting recognition.
- External font loading could stall a browser navigation. Fonts are now bundled locally through npm.
- An unclear child-count correction could leave an older booking summary confirmable. A clarification state now blocks confirmation until corrected input arrives.
- Synthetic speech events prove application wiring, not actual microphone recognition quality or unrestricted Urdu. Physical audio remains a final manual acceptance test.

## Token usage and evidence

The initial chat interface did not expose token counters. A later local audit found genuine `event_msg/token_count` telemetry in this development chat's Codex rollout log. Sanitized records are included in [token-usage.json](docs/ai-usage/token-usage.json). Only timestamp, event ordinal and token counters are exported; prompts, account/rate-limit details and credentials are excluded.

The JSON `last_event` is the authoritative snapshot for the captured portion of this chat. Its cumulative totals include repeated input/context and cached input, so these are not unique tokens of source code, nor a billing estimate. Cached input is a subset of input; reasoning output is a subset of output. Do not add those subsets again. Later development after the snapshot is excluded until re-exported.

| Tool | Activity | Measured token count |
| --- | --- | --- |
| Codex | Captured cumulative development-chat telemetry | See `last_event.total_token_usage` in the attached JSON log |
| Image Generation | One concept generation | Not exposed |
| Runtime assistant | Zero LLM decision calls | Not a development token count |

One UI concept was generated on 2026-10-26 and reviewed in this development chat. It is design guidance, not a runtime image dependency; the final interface is React/CSS with locally bundled fonts.

Refresh the sanitized evidence with `python scripts/export_ai_usage.py <path-to-this-chat-rollout.jsonl>`. Do not commit the original full chat log. The accompanying usage summary records the latest captured measured counts.
