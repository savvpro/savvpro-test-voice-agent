# Authentic usage evidence

`token-usage.json` contains genuine sanitized Codex token-count events from this development chat. `usage-summary.md` lists the latest captured counts and timestamp. These are snapshot totals, including repeated/cached context, not a billing estimate or a claim to include later turns. Image-generation tokens are not separately exposed.

The exporter in `scripts/export_ai_usage.py` copies usage counters only; it excludes chat contents, credentials, account data and rate-limit information. Raw full session logs must not be committed.
