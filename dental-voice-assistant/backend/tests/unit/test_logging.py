"""Unit tests — logging_config.py and app.logging."""

from __future__ import annotations

import json
import logging

from app.logging import JsonFormatter, configure_logging, mask_phone


def test_mask_all_but_last_4() -> None:
    assert mask_phone("03001234567") == "*******4567"


def test_mask_short_phone() -> None:
    assert mask_phone("1234") == "1234"  # 4 digits → nothing masked


def test_mask_with_dashes() -> None:
    result = mask_phone("+1-800-555-0199")
    # Last 4 digits = 0199; earlier digits masked
    assert result.endswith("0199")
    assert "*" in result


def test_mask_preserves_non_digit_chars() -> None:
    result = mask_phone("0300-000-0001")
    # Dashes should be preserved in position
    assert "-" in result


def test_json_formatter():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message with extra",
        args=(),
        exc_info=None,
    )
    record.custom_field = "custom_val"  # type: ignore[attr-defined]

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["msg"] == "Test message with extra"
    assert parsed["custom_field"] == "custom_val"
    assert "ts" in parsed


def test_json_formatter_with_exception():
    formatter = JsonFormatter()
    try:
        raise ValueError("Something broke")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=20,
        msg="Error occurred",
        args=(),
        exc_info=exc_info,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "ERROR"
    assert "exc" in parsed
    assert "ValueError: Something broke" in parsed["exc"]


def test_configure_logging():
    configure_logging("debug")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) > 0
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
