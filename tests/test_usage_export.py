import json
from pathlib import Path

from scripts.export_ai_usage import extract


def test_export_omits_prompts_secrets_and_does_not_sum_counters(tmp_path: Path) -> None:
    path = tmp_path / "fake-session.jsonl"
    records = [
        {"type": "response_item", "payload": {"text": "SECRET_PROMPT"}},
        {
            "type": "event_msg",
            "timestamp": "first",
            "payload": {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 10}}},
        },
        {
            "type": "event_msg",
            "timestamp": "last",
            "payload": {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 25}}},
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")
    result = extract(path)
    assert result["last_reported_totals"] == {"total_tokens": 25}
    assert result["cutoff_utc"] == "last"
    assert "SECRET_PROMPT" not in json.dumps(result)
