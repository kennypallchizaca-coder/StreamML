"""Environment-only configuration for the online API."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _origins_env() -> tuple[str, ...]:
    raw = os.getenv("STREAMML_ALLOWED_ORIGINS", "https://localhost")
    return tuple(origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip())


@dataclass(frozen=True)
class Settings:
    root_dir: Path = ROOT
    database_path: Path = ROOT / "deployment" / "streamml.sqlite3"
    allowed_origins: tuple[str, ...] = ("https://localhost",)
    session_cookie_name: str = "streamml_session"
    session_ttl_seconds: int = 8 * 60 * 60
    connector_ttl_seconds: int = 30 * 24 * 60 * 60
    pairing_ttl_seconds: int = 5 * 60
    cookie_secure: bool = True
    enforce_https: bool = True
    token_secret: str = ""
    media_auth_secret: str = ""
    mediamtx_public_base: str = "https://localhost/media"
    mediamtx_rtmp_publish_base: str = ""
    bootstrap_email: str = ""
    bootstrap_password: str = ""
    login_limit: int = 8
    pairing_limit: int = 10
    telemetry_limit: int = 240
    rate_window_seconds: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        database = Path(os.getenv("STREAMML_DATABASE_PATH", str(ROOT / "deployment" / "streamml.sqlite3")))
        if not database.is_absolute():
            database = ROOT / database
        return cls(
            root_dir=ROOT,
            database_path=database.resolve(),
            allowed_origins=_origins_env(),
            session_cookie_name=os.getenv("STREAMML_SESSION_COOKIE", "streamml_session"),
            session_ttl_seconds=int(os.getenv("STREAMML_SESSION_TTL_SECONDS", str(8 * 60 * 60))),
            connector_ttl_seconds=int(os.getenv("STREAMML_CONNECTOR_TTL_SECONDS", str(30 * 24 * 60 * 60))),
            pairing_ttl_seconds=int(os.getenv("STREAMML_PAIRING_TTL_SECONDS", "300")),
            cookie_secure=_bool_env("STREAMML_COOKIE_SECURE", True),
            enforce_https=_bool_env("STREAMML_ENFORCE_HTTPS", True),
            token_secret=os.getenv("STREAMML_TOKEN_SECRET", ""),
            media_auth_secret=os.getenv("STREAMML_MEDIA_AUTH_SECRET", ""),
            mediamtx_public_base=os.getenv("STREAMML_MEDIAMTX_PUBLIC_BASE", "https://localhost/media").rstrip("/"),
            mediamtx_rtmp_publish_base=os.getenv("STREAMML_MEDIAMTX_RTMP_PUBLISH_BASE", "").rstrip("/"),
            bootstrap_email=os.getenv("STREAMML_BOOTSTRAP_EMAIL", "").strip().lower(),
            bootstrap_password=os.getenv("STREAMML_BOOTSTRAP_PASSWORD", ""),
            login_limit=int(os.getenv("STREAMML_LOGIN_RATE_LIMIT", "8")),
            pairing_limit=int(os.getenv("STREAMML_PAIRING_RATE_LIMIT", "10")),
            telemetry_limit=int(os.getenv("STREAMML_TELEMETRY_RATE_LIMIT", "240")),
            rate_window_seconds=int(os.getenv("STREAMML_RATE_WINDOW_SECONDS", "60")),
        )

    def validate_runtime(self) -> None:
        if len(self.token_secret) < 32:
            raise RuntimeError("STREAMML_TOKEN_SECRET must contain at least 32 characters.")
        if len(self.media_auth_secret) < 32:
            raise RuntimeError("STREAMML_MEDIA_AUTH_SECRET must contain at least 32 characters.")
        if not self.allowed_origins or "*" in self.allowed_origins:
            raise RuntimeError("STREAMML_ALLOWED_ORIGINS must be an explicit non-wildcard allowlist.")
        if bool(self.bootstrap_email) != bool(self.bootstrap_password):
            raise RuntimeError("Bootstrap email and password must be configured together.")
        if self.bootstrap_password and len(self.bootstrap_password) < 12:
            raise RuntimeError("STREAMML_BOOTSTRAP_PASSWORD must contain at least 12 characters.")
