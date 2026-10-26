"""Export only token metadata from a user-selected Codex JSONL session log."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def extract(path: Path) -> dict[str, object]:
    events = []
    models = set()
    with path.open(encoding="utf-8") as source:
        for line in source:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = record.get("payload", {})
            if record.get("type") == "turn_context" and payload.get("model"):
                models.add(payload["model"])
            if record.get("type") != "event_msg" or payload.get("type") != "token_count":
                continue
            info = payload.get("info") or {}
            if not info.get("total_token_usage"):
                continue
            events.append(
                {
                    "timestamp": record.get("timestamp"),
                    "total_token_usage": info["total_token_usage"],
                    "last_token_usage": info.get("last_token_usage"),
                }
            )
    return {
        "schema_version": 1,
        "tool": "Codex",
        "models_reported": sorted(models),
        "exported_at_utc": datetime.now(UTC).isoformat(),
        "source_file": path.name,
        "cutoff_utc": events[-1]["timestamp"] if events else None,
        "last_reported_totals": events[-1]["total_token_usage"] if events else None,
        "notes": [
            "Cumulative counters: use the last report, never sum these totals.",
            "Cached input is part of input, not an additional total.",
            "Only token metadata is exported; prompts, tool output, credentials, and rate-limit account details are excluded.",
            "Image generation and separate reviewer/documenter sessions may not be included in this source's counters.",
        ],
        "events": events,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("docs/ai-usage/codex-token-counts.json")
    )
    args = parser.parse_args()
    result = extract(args.session)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "cutoff": result["cutoff_utc"],
                "totals": result["last_reported_totals"],
            }
        )
    )


if __name__ == "__main__":
    main()
