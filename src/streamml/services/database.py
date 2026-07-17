"""Persistent SQLite store with tenant-scoped queries and hashed credentials."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid

from src.streamml.security.auth import utc_now_iso
from src.streamml.security.crypto import hash_password, redact_mapping


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    stream_id TEXT NOT NULL UNIQUE,
    configuration_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    preferences_json TEXT NOT NULL,
    stream_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pairing_codes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    used_at TEXT
);
CREATE TABLE IF NOT EXISTS connectors (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT
);
CREATE TABLE IF NOT EXISTS telemetry (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    connector_id TEXT NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    observed_at TEXT NOT NULL,
    source TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    network_json TEXT,
    unsupported_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(connector_id, sequence)
);
CREATE INDEX IF NOT EXISTS telemetry_session_idx ON telemetry(user_id, session_id, observed_at DESC);
CREATE TABLE IF NOT EXISTS predictions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    model_role TEXT NOT NULL,
    model_version TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    blocked_reason TEXT,
    input_fingerprint TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS predictions_session_idx ON predictions(user_id, session_id, created_at DESC);
CREATE TABLE IF NOT EXISTS agent_states (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    state_json TEXT NOT NULL,
    last_decision_json TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS control_commands (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    connector_id TEXT REFERENCES connectors(id) ON DELETE SET NULL,
    command_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    acknowledged_at TEXT,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS control_commands_pending_idx
ON control_commands(session_id, status, created_at);
CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    actor_type TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    outcome TEXT NOT NULL,
    client_ip TEXT,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

LATEST_SCHEMA_VERSION = 3


def _expiry(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


DEFAULT_PREFERENCES = {
    "language": "es",
    "timezone": "auto",
    "dark_mode": True,
    "alert_detail": "normal",
}
DEFAULT_STREAM_SETTINGS = {
    "preferred_resolution": "1080p",
    "preferred_profile": "high",
    "platform": "youtube",
    "live_scene": "StreamML Live",
    "backup_scene": "StreamML Backup",
    "network_probe_interval_seconds": 5,
    "network_probe_bytes": 262144,
}


def _json_object(raw: str | None, defaults: dict[str, Any]) -> dict[str, Any]:
    """Read a persisted settings object without letting a bad row break the UI."""

    try:
        loaded = json.loads(raw or "{}")
    except (TypeError, json.JSONDecodeError):
        loaded = {}
    return {**defaults, **(loaded if isinstance(loaded, dict) else {})}


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, factory=_ClosingConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(1,?,?)",
                ("baseline_schema", utc_now_iso()),
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(telemetry)").fetchall()
            }
            if "network_json" not in columns:
                connection.execute("ALTER TABLE telemetry ADD COLUMN network_json TEXT")
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(2,?,?)",
                ("telemetry_network_metrics", utc_now_iso()),
            )
            user_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()
            }
            if "display_name" not in user_columns:
                connection.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT ''")
            session_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
            }
            if "configuration_json" not in session_columns:
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN configuration_json TEXT NOT NULL DEFAULT '{}'"
                )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(3,?,?)",
                ("gui_settings_and_profiles", utc_now_iso()),
            )

    def schema_version(self) -> int:
        try:
            with self._connect() as connection:
                row = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
            return int(row[0]) if row else 0
        except sqlite3.Error:
            return 0

    def integrity_check(self) -> bool:
        try:
            with self._connect() as connection:
                row = connection.execute("PRAGMA quick_check").fetchone()
            return bool(row and row[0] == "ok")
        except sqlite3.Error:
            return False

    def cleanup_expired_credentials(self) -> int:
        """Remove expired or revoked short-lived credentials without deleting stream history."""

        now = utc_now_iso()
        with self._connect() as connection:
            tokens = connection.execute(
                "DELETE FROM auth_tokens WHERE expires_at<=? OR revoked_at IS NOT NULL", (now,)
            ).rowcount
            pairings = connection.execute(
                "DELETE FROM pairing_codes WHERE expires_at<=? OR used_at IS NOT NULL", (now,)
            ).rowcount
        return tokens + pairings

    def ping(self) -> bool:
        try:
            with self._connect() as connection:
                return connection.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False

    def create_user_if_missing(self, email: str, password: str) -> dict[str, Any]:
        existing = self.get_user_by_email(email)
        if existing:
            return existing
        user_id = str(uuid.uuid4())
        created_at = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)",
                (user_id, email, hash_password(password), created_at),
            )
        return self.get_user_by_email(email) or {}

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def update_user_profile(
        self, user_id: str, *, display_name: str, new_password: str | None = None
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            if new_password is None:
                connection.execute(
                    "UPDATE users SET display_name=? WHERE id=?", (display_name, user_id)
                )
            else:
                connection.execute(
                    "UPDATE users SET display_name=?,password_hash=? WHERE id=?",
                    (display_name, hash_password(new_password), user_id),
                )
        return self.get_user_by_id(user_id)

    def delete_user(self, user_id: str) -> bool:
        with self._connect() as connection:
            deleted = connection.execute("DELETE FROM users WHERE id=?", (user_id,))
        return deleted.rowcount == 1

    def save_auth_token(self, user_id: str, token_hash: str, ttl_seconds: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO auth_tokens(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                (token_hash, user_id, _expiry(ttl_seconds), utc_now_iso()),
            )

    def revoke_auth_token(self, token_hash: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE auth_tokens SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                (utc_now_iso(), token_hash),
            )

    def revoke_other_auth_tokens(self, user_id: str, current_token_hash: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE auth_tokens SET revoked_at=?
                   WHERE user_id=? AND token_hash<>? AND revoked_at IS NULL""",
                (utc_now_iso(), user_id, current_token_hash),
            )

    def user_from_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT u.id,u.email,u.display_name,u.created_at FROM auth_tokens t
                   JOIN users u ON u.id=t.user_id
                   WHERE t.token_hash=? AND t.revoked_at IS NULL AND t.expires_at>?""",
                (token_hash, utc_now_iso()),
            ).fetchone()
        return dict(row) if row else None

    def create_session(
        self, user_id: str, name: str, configuration: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        now = utc_now_iso()
        stream_id = "stream-" + uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO sessions
                   (id,user_id,name,status,stream_id,configuration_json,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (
                    session_id, user_id, name, "created", stream_id,
                    json.dumps(configuration or {}, separators=(",", ":"), sort_keys=True), now, now,
                ),
            )
        return self.get_session(user_id, session_id) or {}

    def get_session(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT id,user_id,name,status,stream_id,configuration_json,created_at,updated_at
                   FROM sessions WHERE id=? AND user_id=?""",
                (session_id, user_id),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["configuration"] = _json_object(result.pop("configuration_json", None), {})
        return result

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id,user_id,name,status,stream_id,configuration_json,created_at,updated_at
                   FROM sessions WHERE user_id=? ORDER BY created_at DESC""",
                (user_id,),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["configuration"] = _json_object(item.pop("configuration_json", None), {})
            results.append(item)
        return results

    def update_session_configuration(
        self, user_id: str, session_id: str, changes: dict[str, Any]
    ) -> dict[str, Any] | None:
        session = self.get_session(user_id, session_id)
        if not session:
            return None
        configuration = {**session.get("configuration", {}), **changes}
        with self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET configuration_json=?,updated_at=? WHERE id=? AND user_id=?",
                (
                    json.dumps(configuration, separators=(",", ":"), sort_keys=True),
                    utc_now_iso(), session_id, user_id,
                ),
            )
        return self.get_session(user_id, session_id)

    def get_user_settings(self, user_id: str) -> dict[str, Any]:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO user_settings(user_id,preferences_json,stream_json,updated_at)
                   VALUES(?,?,?,?)""",
                (
                    user_id,
                    json.dumps(DEFAULT_PREFERENCES, separators=(",", ":"), sort_keys=True),
                    json.dumps(DEFAULT_STREAM_SETTINGS, separators=(",", ":"), sort_keys=True),
                    now,
                ),
            )
            row = connection.execute(
                "SELECT preferences_json,stream_json,updated_at FROM user_settings WHERE user_id=?", (user_id,)
            ).fetchone()
        assert row is not None
        return {
            "preferences": _json_object(row["preferences_json"], DEFAULT_PREFERENCES),
            "stream": _json_object(row["stream_json"], DEFAULT_STREAM_SETTINGS),
            "updated_at": row["updated_at"],
        }

    def update_user_settings(
        self, user_id: str, *, preferences: dict[str, Any] | None = None,
        stream: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = self.get_user_settings(user_id)
        updated_preferences = {**current["preferences"], **(preferences or {})}
        updated_stream = {**current["stream"], **(stream or {})}
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """UPDATE user_settings SET preferences_json=?,stream_json=?,updated_at=? WHERE user_id=?""",
                (
                    json.dumps(updated_preferences, separators=(",", ":"), sort_keys=True),
                    json.dumps(updated_stream, separators=(",", ":"), sort_keys=True), now, user_id,
                ),
            )
        return self.get_user_settings(user_id)

    def list_connectors(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id,session_id,name,version,created_at,last_seen_at,expires_at
                   FROM connectors WHERE user_id=? ORDER BY created_at DESC""",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_user_history(self, user_id: str) -> int:
        """Delete transmission data while preserving the account and saved defaults."""

        with self._connect() as connection:
            deleted = connection.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        return deleted.rowcount

    def export_user_data(self, user_id: str) -> dict[str, Any]:
        user = self.get_user_by_id(user_id)
        if not user:
            return {}
        user.pop("password_hash", None)
        sessions = self.list_sessions(user_id)
        for session in sessions:
            session_id = session["id"]
            session["telemetry"] = self.latest_telemetry(user_id, session_id)
            session["predictions"] = self.recent_predictions(user_id, session_id, limit=100)
        return {
            "exported_at": utc_now_iso(),
            "user": user,
            "settings": self.get_user_settings(user_id),
            "sessions": sessions,
        }

    def update_session_status(self, user_id: str, session_id: str, status: str) -> None:
        if status not in {"created", "ready", "active", "offline"}:
            raise ValueError("Unsupported session status.")
        with self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET status=?,updated_at=? WHERE id=? AND user_id=?",
                (status, utc_now_iso(), session_id, user_id),
            )

    def create_pairing_code(self, user_id: str, session_id: str, code_hash: str, ttl_seconds: int) -> str:
        pairing_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO pairing_codes(id,user_id,session_id,code_hash,expires_at,created_at) VALUES(?,?,?,?,?,?)",
                (pairing_id, user_id, session_id, code_hash, _expiry(ttl_seconds), utc_now_iso()),
            )
        return pairing_id

    def consume_pairing_code(
        self,
        code_hash: str,
        connector_name: str,
        connector_version: str,
        connector_token_hash: str,
        token_ttl_seconds: int,
    ) -> dict[str, Any] | None:
        now = utc_now_iso()
        connector_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pairing = connection.execute(
                "SELECT * FROM pairing_codes WHERE code_hash=? AND used_at IS NULL AND expires_at>?",
                (code_hash, now),
            ).fetchone()
            if not pairing:
                connection.rollback()
                return None
            updated = connection.execute(
                "UPDATE pairing_codes SET used_at=? WHERE id=? AND used_at IS NULL",
                (now, pairing["id"]),
            )
            if updated.rowcount != 1:
                connection.rollback()
                return None
            connection.execute(
                """INSERT INTO connectors
                   (id,user_id,session_id,name,version,token_hash,expires_at,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (
                    connector_id, pairing["user_id"], pairing["session_id"], connector_name,
                    connector_version, connector_token_hash, _expiry(token_ttl_seconds), now,
                ),
            )
            connection.commit()
        return {
            "id": connector_id,
            "user_id": pairing["user_id"],
            "session_id": pairing["session_id"],
            "name": connector_name,
            "version": connector_version,
        }

    def connector_from_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM connectors WHERE token_hash=? AND expires_at>?",
                (token_hash, utc_now_iso()),
            ).fetchone()
        return dict(row) if row else None

    def store_telemetry(
        self,
        *,
        user_id: str,
        session_id: str,
        connector_id: str,
        sequence: int,
        observed_at: str,
        source: str,
        metrics: dict[str, Any],
        network: dict[str, Any] | None,
        unsupported: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        telemetry_id = str(uuid.uuid4())
        created_at = utc_now_iso()
        with self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO telemetry
                       (id,user_id,session_id,connector_id,sequence,observed_at,source,metrics_json,network_json,unsupported_json,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        telemetry_id, user_id, session_id, connector_id, sequence, observed_at, source,
                        json.dumps(metrics, separators=(",", ":"), sort_keys=True),
                        json.dumps(network, separators=(",", ":"), sort_keys=True) if network is not None else None,
                        json.dumps(unsupported, separators=(",", ":"), sort_keys=True), created_at,
                    ),
                )
                connection.execute("UPDATE connectors SET last_seen_at=? WHERE id=?", (created_at, connector_id))
                inserted = True
            except sqlite3.IntegrityError:
                row = connection.execute(
                    "SELECT * FROM telemetry WHERE connector_id=? AND sequence=?", (connector_id, sequence)
                ).fetchone()
                if not row:
                    raise
                telemetry_id = row["id"]
                observed_at = row["observed_at"]
                source = row["source"]
                metrics = json.loads(row["metrics_json"])
                network = json.loads(row["network_json"]) if row["network_json"] else None
                unsupported = json.loads(row["unsupported_json"])
                created_at = row["created_at"]
                inserted = False
        return {
            "id": telemetry_id,
            "session_id": session_id,
            "connector_id": connector_id,
            "sequence": sequence,
            "observed_at": observed_at,
            "source": source,
            "metrics": metrics,
            "network": network,
            "unsupported": unsupported,
            "created_at": created_at,
        }, inserted

    def latest_telemetry(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM telemetry WHERE user_id=? AND session_id=?
                   ORDER BY observed_at DESC, sequence DESC LIMIT 1""",
                (user_id, session_id),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["metrics"] = json.loads(result.pop("metrics_json"))
        raw_network = result.pop("network_json", None)
        result["network"] = json.loads(raw_network) if raw_network else None
        result["unsupported"] = json.loads(result.pop("unsupported_json"))
        return result

    def recent_network_telemetry(
        self, user_id: str, session_id: str, limit: int
    ) -> list[dict[str, Any]]:
        """Return compatible network samples in chronological order."""

        with self._connect() as connection:
            rows = connection.execute(
                """SELECT observed_at,network_json FROM telemetry
                   WHERE user_id=? AND session_id=? AND network_json IS NOT NULL
                   ORDER BY observed_at DESC, sequence DESC LIMIT ?""",
                (user_id, session_id, limit),
            ).fetchall()
        results = [
            {"observed_at": row["observed_at"], "network": json.loads(row["network_json"])}
            for row in reversed(rows)
        ]
        return results

    def load_agent_state(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM agent_states WHERE user_id=? AND session_id=?",
                (user_id, session_id),
            ).fetchone()
        return json.loads(row["state_json"]) if row else None

    def save_agent_state(
        self,
        user_id: str,
        session_id: str,
        state: dict[str, Any],
        decision: dict[str, Any],
    ) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO agent_states(session_id,user_id,state_json,last_decision_json,updated_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(session_id) DO UPDATE SET
                     state_json=excluded.state_json,
                     last_decision_json=excluded.last_decision_json,
                     updated_at=excluded.updated_at""",
                (
                    session_id,
                    user_id,
                    json.dumps(state, separators=(",", ":"), sort_keys=True),
                    json.dumps(decision, separators=(",", ":"), sort_keys=True),
                    now,
                ),
            )

    def latest_agent_decision(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT last_decision_json,updated_at FROM agent_states
                   WHERE user_id=? AND session_id=?""",
                (user_id, session_id),
            ).fetchone()
        if not row or not row["last_decision_json"]:
            return None
        result = json.loads(row["last_decision_json"])
        result["updated_at"] = row["updated_at"]
        return result

    def enqueue_control_command(
        self,
        *,
        user_id: str,
        session_id: str,
        connector_id: str | None,
        command_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        command_id = str(uuid.uuid4())
        created_at = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO control_commands
                   (id,user_id,session_id,connector_id,command_type,payload_json,status,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (
                    command_id, user_id, session_id, connector_id, command_type,
                    json.dumps(payload, separators=(",", ":"), sort_keys=True),
                    "pending", created_at,
                ),
            )
        return {
            "id": command_id,
            "session_id": session_id,
            "command_type": command_type,
            "payload": payload,
            "status": "pending",
            "created_at": created_at,
        }

    def pending_control_command(self, connector_id: str, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM control_commands
                   WHERE session_id=? AND status='pending'
                     AND (connector_id IS NULL OR connector_id=?)
                   ORDER BY created_at ASC LIMIT 1""",
                (session_id, connector_id),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def acknowledge_control_command(
        self, connector_id: str, command_id: str, *, success: bool, error_message: str | None
    ) -> bool:
        status = "completed" if success else "failed"
        with self._connect() as connection:
            command = connection.execute(
                """SELECT user_id,session_id,command_type,payload_json FROM control_commands
                   WHERE id=? AND status='pending' AND (connector_id IS NULL OR connector_id=?)""",
                (command_id, connector_id),
            ).fetchone()
            if not command:
                return False
            updated = connection.execute(
                """UPDATE control_commands
                   SET status=?,acknowledged_at=?,error_message=?
                   WHERE id=? AND status='pending' AND (connector_id IS NULL OR connector_id=?)""",
                (status, utc_now_iso(), error_message, command_id, connector_id),
            )
            if not success:
                state_row = connection.execute(
                    "SELECT state_json FROM agent_states WHERE user_id=? AND session_id=?",
                    (command["user_id"], command["session_id"]),
                ).fetchone()
                if state_row:
                    state = json.loads(state_row["state_json"])
                    payload = json.loads(command["payload_json"])
                    if command["command_type"] == "set_profile":
                        previous = payload.get("previous_profile")
                        if previous in {"low", "medium", "high"}:
                            state["current_profile"] = previous
                    elif command["command_type"] in {"activate_backup", "restore_live"}:
                        state["backup_active"] = bool(payload.get("previous_backup_active"))
                    connection.execute(
                        "UPDATE agent_states SET state_json=?,updated_at=? WHERE user_id=? AND session_id=?",
                        (
                            json.dumps(state, separators=(",", ":"), sort_keys=True),
                            utc_now_iso(), command["user_id"], command["session_id"],
                        ),
                    )
        return updated.rowcount == 1

    def store_prediction(
        self,
        *,
        user_id: str,
        session_id: str,
        model_role: str,
        model_version: str,
        status: str,
        result: dict[str, Any] | None,
        blocked_reason: str | None,
        input_fingerprint: str | None,
    ) -> dict[str, Any]:
        prediction_id = str(uuid.uuid4())
        created_at = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO predictions
                   (id,user_id,session_id,model_role,model_version,status,result_json,blocked_reason,input_fingerprint,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    prediction_id, user_id, session_id, model_role, model_version, status,
                    json.dumps(result, separators=(",", ":"), sort_keys=True) if result is not None else None,
                    blocked_reason, input_fingerprint, created_at,
                ),
            )
        return {
            "id": prediction_id, "session_id": session_id, "model_role": model_role,
            "model_version": model_version, "status": status, "result": result,
            "blocked_reason": blocked_reason, "created_at": created_at,
        }

    def recent_predictions(self, user_id: str, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id,session_id,model_role,model_version,status,result_json,blocked_reason,created_at
                   FROM predictions WHERE user_id=? AND session_id=? ORDER BY created_at DESC LIMIT ?""",
                (user_id, session_id, limit),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["result"] = json.loads(item.pop("result_json")) if item["result_json"] else None
            results.append(item)
        return results

    def record_audit(
        self,
        *,
        actor_type: str,
        action: str,
        outcome: str,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        client_ip: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        safe_details = redact_mapping(details or {})
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO audit_events
                   (id,user_id,actor_type,action,resource_type,resource_id,outcome,client_ip,details_json,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    str(uuid.uuid4()), user_id, actor_type, action, resource_type, resource_id,
                    outcome, client_ip, json.dumps(safe_details, separators=(",", ":"), sort_keys=True), utc_now_iso(),
                ),
            )
