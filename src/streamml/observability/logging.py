"""Structured, redacted application logging."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.streamml.security.crypto import redact_mapping


LOGGER = logging.getLogger("streamml.online")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }
        details = getattr(record, "details", None)
        if details:
            payload["details"] = redact_mapping(details)
        if record.exc_info:
            payload["exception"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def configure_logging() -> None:
    if LOGGER.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def audit_log(event: str, **details: Any) -> None:
    LOGGER.info(event, extra={"event": event, "details": redact_mapping(details)})
