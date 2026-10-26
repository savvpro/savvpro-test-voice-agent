"""Structured JSON logging using the stdlib ``logging`` module.

No external dependency (no structlog).  Every log record is serialised to a
single JSON line containing *timestamp*, *level*, *logger*, *message*, and
any extra fields passed via ``extra={...}``.

PII rules:
- Never log tracking IDs, phone digits, or recipient names.
- Use session IDs and safe labels only.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class _JSONFormatter(logging.Formatter):
    """Emit each record as a single JSON object on one line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach any extra fields the caller passed.
        for key in ("session_id", "state", "action", "rule", "error"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with the JSON formatter.

    Call once at application startup (inside the lifespan function).

    Args:
        level: Python log-level name (``DEBUG``, ``INFO``, …).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.  Always use this instead of ``logging.getLogger``
    directly so log output goes through our JSON formatter.
    """
    return logging.getLogger(name)
