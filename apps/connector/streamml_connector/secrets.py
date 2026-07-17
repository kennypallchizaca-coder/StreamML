"""Secret acquisition and OS-backed token storage.

There is deliberately no plaintext-file fallback. If the host keyring is not
available, the connector fails closed and asks the operator to configure one.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from getpass import getpass
import hashlib
import json
import os

class SecretStorageError(RuntimeError):
    """Raised when a secret cannot be stored securely."""


@dataclass(frozen=True, slots=True)
class ConnectorCredentials:
    access_token: str = field(repr=False)
    connector_id: str | None = None
    session_id: str | None = None


def read_obs_password() -> str:
    """Read the OBS password from the environment or a non-echoing prompt."""

    password = os.getenv("OBS_WEBSOCKET_PASSWORD")
    if password is None:
        password = getpass("OBS WebSocket password: ")
    if not password:
        raise SecretStorageError("An OBS WebSocket password is required.")
    return password


def read_pairing_code(explicit_code: str | None) -> str:
    """Read a one-time linking code without echoing it to the terminal."""

    code = explicit_code if explicit_code is not None else getpass(
        "Temporary StreamML linking code: "
    )
    code = code.strip()
    if not code:
        raise SecretStorageError("A temporary linking code is required.")
    return code


class TokenStore:
    """Persist API credentials in the operating system credential vault."""

    def __init__(self, service: str, api_base_url: str, connector_name: str) -> None:
        self._service = service
        identity = f"{api_base_url}|{connector_name}".encode("utf-8")
        self._account = "connector-" + hashlib.sha256(identity).hexdigest()[:24]

    def load(self) -> ConnectorCredentials | None:
        keyring = _load_keyring()
        try:
            raw = keyring.get_password(self._service, self._account)
        except Exception as exc:
            raise SecretStorageError("The operating system keyring is unavailable.") from exc
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            token = str(data["access_token"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SecretStorageError("Stored connector credentials are invalid.") from exc
        return ConnectorCredentials(
            access_token=token,
            connector_id=data.get("connector_id"),
            session_id=data.get("session_id"),
        )

    def save(self, credentials: ConnectorCredentials) -> None:
        keyring = _load_keyring()
        payload = json.dumps(asdict(credentials), separators=(",", ":"))
        try:
            keyring.set_password(self._service, self._account, payload)
        except Exception as exc:
            raise SecretStorageError(
                "The connector token could not be saved in the operating system keyring."
            ) from exc

    def delete(self) -> None:
        keyring = _load_keyring()
        try:
            keyring.delete_password(self._service, self._account)
        except keyring.errors.PasswordDeleteError:
            return
        except Exception as exc:
            raise SecretStorageError("The stored connector token could not be removed.") from exc


def _load_keyring():
    try:
        import keyring
    except ImportError as exc:
        raise SecretStorageError(
            "The keyring dependency is required; install the connector package before running it."
        ) from exc
    return keyring
