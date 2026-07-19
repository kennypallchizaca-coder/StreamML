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
from typing import Final


class SecretStorageError(RuntimeError):
    """Raised when a secret cannot be stored securely."""


_LOCAL_SETUP_SERVICE: Final = "streamml-local-setup"


class LocalSecretVault:
    """Small typed facade over the operating-system credential vault.

    The setup GUI stores only opaque values here.  It deliberately exposes
    presence checks rather than listing or rendering the stored values.
    """

    _allowed_names = {
        "obs_websocket_password",
        "deployment_token_secret",
        "deployment_media_auth_secret",
        "deployment_bootstrap_password",
        "deployment_restream_config_json",
    }

    def __init__(self, service: str = _LOCAL_SETUP_SERVICE) -> None:
        self._service = service

    def get(self, name: str) -> str | None:
        self._validate_name(name)
        keyring = _load_keyring()
        try:
            return keyring.get_password(self._service, name)
        except Exception as exc:
            raise SecretStorageError("El almacén de credenciales del sistema no está disponible.") from exc

    def has(self, name: str) -> bool:
        return bool(self.get(name))

    def set(self, name: str, value: str) -> None:
        self._validate_name(name)
        if not isinstance(value, str) or not value:
            raise SecretStorageError("No se puede guardar una credencial vacía.")
        keyring = _load_keyring()
        try:
            keyring.set_password(self._service, name, value)
        except Exception as exc:
            raise SecretStorageError("La credencial no se pudo guardar en el almacén seguro del sistema.") from exc

    def delete(self, name: str) -> None:
        self._validate_name(name)
        keyring = _load_keyring()
        try:
            keyring.delete_password(self._service, name)
        except keyring.errors.PasswordDeleteError:
            return
        except Exception as exc:
            raise SecretStorageError("La credencial segura no se pudo eliminar.") from exc

    def _validate_name(self, name: str) -> None:
        if name not in self._allowed_names:
            raise SecretStorageError("Nombre de credencial no permitido.")


@dataclass(frozen=True, slots=True)
class ConnectorCredentials:
    access_token: str = field(repr=False)
    connector_id: str | None = None
    session_id: str | None = None


def read_obs_password() -> str:
    """Read the OBS password from the environment or a non-echoing prompt."""

    password = os.getenv("OBS_WEBSOCKET_PASSWORD")
    if password is None:
        # A password saved through the local GUI never enters a process
        # environment or a plaintext configuration file.
        password = LocalSecretVault().get("obs_websocket_password")
    if password is None:
        password = getpass("OBS WebSocket password: ")
    if not password:
        raise SecretStorageError("An OBS WebSocket password is required.")
    return password


def read_pairing_code(explicit_code: str | None) -> str:
    """Read a one-time linking code without echoing it to the terminal."""

    code = explicit_code if explicit_code is not None else getpass("Temporary StreamML linking code: ")
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
            raise SecretStorageError("The connector token could not be saved in the operating system keyring.") from exc

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
