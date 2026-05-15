from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .utils import ensure_dir, serialize_for_json, sha256_text


class SQLiteCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        ensure_dir(self.path.parent)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER,
                    PRIMARY KEY (namespace, cache_key)
                )
                """
            )
            self._conn.commit()

    @staticmethod
    def make_key(*parts: Any) -> str:
        return sha256_text(json.dumps(serialize_for_json(parts), sort_keys=True, ensure_ascii=False))

    def get_json(self, namespace: str, cache_key: str) -> Any | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, expires_at FROM cache_entries WHERE namespace = ? AND cache_key = ?",
                (namespace, cache_key),
            ).fetchone()
            if not row:
                return None
            expires_at = row["expires_at"]
            if expires_at is not None and int(expires_at) < int(time.time()):
                self._conn.execute(
                    "DELETE FROM cache_entries WHERE namespace = ? AND cache_key = ?",
                    (namespace, cache_key),
                )
                self._conn.commit()
                return None
            return json.loads(row["payload"])

    def set_json(self, namespace: str, cache_key: str, value: Any, ttl_seconds: int | None = None) -> None:
        payload = json.dumps(serialize_for_json(value), ensure_ascii=False)
        expires_at = int(time.time()) + int(ttl_seconds) if ttl_seconds else None
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries (namespace, cache_key, payload, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (namespace, cache_key, payload, int(time.time()), expires_at),
            )
            self._conn.commit()

    def delete_namespace(self, namespace: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache_entries WHERE namespace = ?", (namespace,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

