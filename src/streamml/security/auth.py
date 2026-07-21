"""Funciones de autenticación compartidas por rutas HTTP y WebSocket."""

from __future__ import annotations

from datetime import datetime, timezone
import re


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 254 or not EMAIL_PATTERN.match(normalized):
        raise ValueError("Invalid email address.")
    return normalized


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
