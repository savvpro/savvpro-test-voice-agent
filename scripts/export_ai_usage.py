"""Export only token-count telemetry from this chat; never copy chat or account data."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def export(source: Path, destination: Path):
    events = []
    for line in source.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        payload = entry.get("payload", {})
        if entry.get("type") != "event_msg" or payload.get("type") != "token_count":
            continue
        info = payload.get("info") or {}
        if info.get("total_token_usage"):
            events.append(
                {
                    "timestamp": entry.get("timestamp"),
                    "ordinal": entry.get("ordinal"),
                    "total_token_usage": info["total_token_usage"],
                    "last_token_usage": info.get("last_token_usage"),
                }
            )
    if not events:
        raise SystemExit("No measured token telemetry found; no evidence file written.")
    document = {
        "exported_at": datetime.now(UTC).isoformat(),
        "source": "Local Codex rollout event_msg/token_count records from this development chat",
        "scope": "Cumulative snapshot through last_event.timestamp; repeated prompt and cached input tokens are included, not unique words or a billing estimate. Later work is not included until re-exported. Image generation tokens are not separately exposed.",
        "last_event": events[-1],
        "events": events,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    usage = events[-1]["total_token_usage"]
    destination.with_name("usage-summary.md").write_text(
        "# Measured AI usage snapshot\n\n"
        f"Latest captured event: **{events[-1]['timestamp']}** (UTC). "
        f"Export includes {len(events)} genuine token-count events.\n\n"
        "| Counter | Tokens |\n| --- | ---: |\n"
        f"| Input | {usage['input_tokens']:,} |\n"
        f"| Cached input (subset of input) | {usage.get('cached_input_tokens', 0):,} |\n"
        f"| Output | {usage['output_tokens']:,} |\n"
        f"| Reasoning output (subset of output) | {usage.get('reasoning_output_tokens', 0):,} |\n"
        f"| Total input + output | {usage['total_tokens']:,} |\n\n"
        "These are cumulative development-chat telemetry, including repeated/context and cached tokens. "
        "They are not unique source-code tokens or a billing estimate. Work after this timestamp is excluded. "
        "Image-generation usage is not separately exposed. See token-usage.json for sanitized evidence.\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "events": len(events),
                "latest_timestamp": events[-1]["timestamp"],
                "usage": events[-1]["total_token_usage"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("docs/ai-usage/token-usage.json")
    )
    args = parser.parse_args()
    export(args.source, args.output)
