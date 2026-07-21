"""Credenciales con alcance de sesión para la integración con VDO.Ninja."""

from __future__ import annotations

import hashlib
import hmac


def vdo_bridge_token(secret: str, session_id: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        f"vdo-bridge:{session_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def valid_vdo_bridge_token(secret: str, session_id: str, supplied: str) -> bool:
    return bool(supplied) and hmac.compare_digest(vdo_bridge_token(secret, session_id), supplied)
