"""Structured JSON logging setup and PII helpers."""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from typing import Any

# ── PII helpers ───────────────────────────────────────────────────────────────

_PHONE_RE = re.compile(r"\d")


def mask_phone(phone: str) -> str:
    """Mask all but the last 4 digits of *phone*.

    Examples
    --------
    >>> mask_phone("03001234567")
    '*******4567'
    >>> mask_phone("+1-800-555-0199")
    '***-***-***0199'
    """
    digits_seen = 0
    chars = list(phone)
    # count total digits
    total_digits = sum(1 for c in chars if c.isdigit())
    keep = min(4, total_digits)
    mask_up_to = total_digits - keep

    result: list[str] = []
    for ch in chars:
        if ch.isdigit():
            digits_seen += 1
            if digits_seen <= mask_up_to:
                result.append("*")
            else:
                result.append(ch)
        else:
            result.append(ch)
    return "".join(result)


# ── JSON formatter ────────────────────────────────────────────────────────────


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_object: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log_object["exc"] = self.formatException(record.exc_info)
        # Merge any extra fields attached to the record
        for key, value in record.__dict__.items():
            if key not in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "id",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                "taskName",
            }:
                log_object[key] = value
        return json.dumps(log_object, default=str)


# ── Setup helper ──────────────────────────────────────────────────────────────


def configure_logging(level: str = "info") -> None:
    """Configure root logger to emit structured JSON to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
