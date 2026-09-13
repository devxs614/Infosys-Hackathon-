"""Persistent local identity store owned by the Raspberry Pi FastAPI process."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class AuthConflictError(ValueError):
    pass


class AuthInvalidCredentialsError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _password_digest(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 210_000).hex()


class AuthStore:
    """SQLite-backed users and opaque sessions; no browser owns user records."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    def connect(self) -> None:
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    role TEXT NOT NULL,
                    vehicle TEXT,
                    avatar_url TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            """)
            self._connection.commit()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _db(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("Auth store has not been connected")
        return self._connection

    @staticmethod
    def _public(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"],
            "vehicle": row["vehicle"] or None, "avatar_url": row["avatar_url"] or None,
            "created_at": row["created_at"],
        }

    def _issue_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._db().execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user_id, _now()))
            self._db().commit()
        return token

    def register(self, *, name: str, email: str, password: str, role: str, vehicle: str | None = None, avatar_url: str | None = None) -> dict:
        normalized_email = email.strip().lower()
        salt = secrets.token_hex(16)
        user_id = str(uuid4())
        with self._lock:
            try:
                self._db().execute(
                    """INSERT INTO users (id, name, email, password_hash, password_salt, role, vehicle, avatar_url, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, name.strip(), normalized_email, _password_digest(password, salt), salt, role, vehicle or None, avatar_url or None, _now()),
                )
                self._db().commit()
            except sqlite3.IntegrityError as exc:
                raise AuthConflictError("An account with this email already exists") from exc
            row = self._db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return {"user": self._public(row), "session_token": self._issue_session(user_id)}

    def login(self, *, email: str, password: str) -> dict:
        with self._lock:
            row = self._db().execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        if row is None or not hmac.compare_digest(row["password_hash"], _password_digest(password, row["password_salt"])):
            raise AuthInvalidCredentialsError("Invalid email or password")
        return {"user": self._public(row), "session_token": self._issue_session(row["id"])}

    def authenticate_session(self, user_id: str | None, token: str | None) -> dict | None:
        if not user_id or not token:
            return None
        with self._lock:
            row = self._db().execute(
                """SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id
                   WHERE sessions.token = ? AND sessions.user_id = ?""",
                (token, user_id),
            ).fetchone()
        return self._public(row) if row else None
