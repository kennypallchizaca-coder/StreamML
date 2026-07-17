"""Structured, redacted application logging."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.streamml.security.crypto import redact_mapping


LOGGER = logging.getLogger("streamml.online")


def configure_logging() -> None:
    if LOGGER.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def audit_log(event: str, **details: Any) -> None:
    safe = redact_mapping(details)
    LOGGER.info("%s %s", event, json.dumps(safe, sort_keys=True, separators=(",", ":")))
