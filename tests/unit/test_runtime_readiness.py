from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from apps.api.config import Settings
from src.streamml.security.crypto import redact_mapping
from src.streamml.services.database import Database, LATEST_SCHEMA_VERSION


def test_legacy_database_is_migrated_and_integrity_checked(tmp_path: Path):
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE sessions (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
          status TEXT NOT NULL, stream_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL);
        CREATE TABLE telemetry (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, session_id TEXT NOT NULL,
          connector_id TEXT NOT NULL, sequence INTEGER NOT NULL, observed_at TEXT NOT NULL,
          source TEXT NOT NULL, metrics_json TEXT NOT NULL, unsupported_json TEXT NOT NULL,
          created_at TEXT NOT NULL);
        """
    )
    connection.close()

    database = Database(path)
    database.initialize()

    assert database.schema_version() == LATEST_SCHEMA_VERSION
    assert database.integrity_check() is True
    with sqlite3.connect(path) as migrated:
        assert "display_name" in {row[1] for row in migrated.execute("PRAGMA table_info(users)")}
        assert "configuration_json" in {row[1] for row in migrated.execute("PRAGMA table_info(sessions)")}
        assert "network_json" in {row[1] for row in migrated.execute("PRAGMA table_info(telemetry)")}


def test_production_rejects_insecure_runtime_settings(tmp_path: Path):
    settings = Settings(
        environment="production",
        database_path=tmp_path / "test.sqlite3",
        token_secret="t" * 32,
        media_auth_secret="m" * 32,
        allowed_origins=("http://localhost",),
        mediamtx_public_base="http://localhost/media",
        cookie_secure=False,
        enforce_https=False,
    )
    with pytest.raises(RuntimeError, match="secure cookies"):
        settings.validate_runtime()
    assert settings.production_controls_ready() is False


def test_nested_and_prefixed_secrets_are_redacted():
    safe = redact_mapping({"deployment_token_secret": "hidden", "nested": {"password": "hidden"}})
    assert safe == {"deployment_token_secret": "[REDACTED]", "nested": {"password": "[REDACTED]"}}
