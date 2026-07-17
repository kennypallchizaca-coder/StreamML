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
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
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
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id, created_at DESC);
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


def _expiry(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


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

    def user_from_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT u.id,u.email,u.created_at FROM auth_tokens t
                   JOIN users u ON u.id=t.user_id
                   WHERE t.token_hash=? AND t.revoked_at IS NULL AND t.expires_at>?""",
                (token_hash, utc_now_iso()),
            ).fetchone()
        return dict(row) if row else None

    def create_session(self, user_id: str, name: str) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        now = utc_now_iso()
        stream_id = "stream-" + uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO sessions(id,user_id,name,status,stream_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (session_id, user_id, name, "created", stream_id, now, now),
            )
        return self.get_session(user_id, session_id) or {}

    def get_session(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id,user_id,name,status,stream_id,created_at,updated_at FROM sessions WHERE id=? AND user_id=?",
                (session_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id,user_id,name,status,stream_id,created_at,updated_at FROM sessions WHERE user_id=? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

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
        unsupported: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        telemetry_id = str(uuid.uuid4())
        created_at = utc_now_iso()
        with self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO telemetry
                       (id,user_id,session_id,connector_id,sequence,observed_at,source,metrics_json,unsupported_json,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        telemetry_id, user_id, session_id, connector_id, sequence, observed_at, source,
                        json.dumps(metrics, separators=(",", ":"), sort_keys=True),
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
        result["unsupported"] = json.loads(result.pop("unsupported_json"))
        return result

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
