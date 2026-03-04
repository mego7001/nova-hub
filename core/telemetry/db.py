from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def telemetry_db_path(workspace_root: str) -> str:
    root = Path(workspace_root)
    return str(root / "runtime" / "telemetry" / "nova_telemetry.sqlite3")


class TelemetryDB:
    def __init__(self, *, workspace_root: str | None = None, db_path: str | None = None) -> None:
        resolved_path = db_path
        if not resolved_path:
            ws = str(workspace_root or os.environ.get("NH_WORKSPACE") or "").strip()
            if not ws:
                ws = os.path.abspath(os.path.join(os.getcwd(), "workspace"))
            resolved_path = telemetry_db_path(ws)
        self.path = os.path.abspath(str(resolved_path))
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with self._lock:
            with self._connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("PRAGMA foreign_keys=ON;")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_meta(
                        schema_version INTEGER NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                current_version = self._schema_version(conn)
                if current_version <= 0:
                    conn.execute(
                        "INSERT INTO schema_meta(schema_version, created_at) VALUES(?, ?)",
                        (SCHEMA_VERSION, _utc_now()),
                    )
                    current_version = SCHEMA_VERSION
                if current_version < SCHEMA_VERSION:
                    conn.execute("DELETE FROM schema_meta")
                    conn.execute(
                        "INSERT INTO schema_meta(schema_version, created_at) VALUES(?, ?)",
                        (SCHEMA_VERSION, _utc_now()),
                    )
                self._apply_schema(conn)
                conn.commit()

    def _schema_version(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT schema_version FROM schema_meta LIMIT 1").fetchone()
        if not row:
            return 0
        try:
            return int(row["schema_version"])
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return 0

    def _apply_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_calls(
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                session_id TEXT,
                project_id TEXT,
                mode TEXT,
                provider TEXT,
                model TEXT,
                profile TEXT,
                request_kind TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cost_usd REAL,
                latency_ms INTEGER,
                status TEXT,
                error_kind TEXT,
                error_msg TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_calls(
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                session_id TEXT,
                project_id TEXT,
                mode TEXT,
                tool_name TEXT,
                latency_ms INTEGER,
                status TEXT,
                error_kind TEXT,
                error_msg TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_runs(
                id TEXT PRIMARY KEY,
                ts_start TEXT NOT NULL,
                ts_end TEXT,
                session_id TEXT,
                project_id TEXT,
                mode TEXT,
                objective TEXT,
                status TEXT,
                qa_passed INTEGER,
                tests_passed INTEGER,
                tests_failed INTEGER,
                notes TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_calls_ts ON llm_calls(ts DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_calls_provider ON llm_calls(provider, ts DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_calls_mode ON llm_calls(mode, request_kind, ts DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_calls_status ON llm_calls(status, error_kind, ts DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_calls_ts ON tool_calls(ts DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_calls_tool ON tool_calls(tool_name, ts DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_ts ON task_runs(ts_start DESC)")

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(sql, tuple(params))
                conn.commit()

    def fetch_one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(sql, tuple(params)).fetchone()
        if row is None:
            return None
        return {str(k): row[k] for k in row.keys()}

    def fetch_all(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(sql, tuple(params)).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append({str(k): row[k] for k in row.keys()})
        return out

    def schema_version(self) -> int:
        row = self.fetch_one("SELECT schema_version FROM schema_meta LIMIT 1")
        if not row:
            return 0
        try:
            return int(row.get("schema_version") or 0)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return 0

    def wal_enabled(self) -> bool:
        row = self.fetch_one("PRAGMA journal_mode;")
        mode = str((row or {}).get("journal_mode") or "").strip().lower()
        return mode == "wal"

    def checkpoint_wal(self, *, truncate: bool = True) -> Dict[str, Any]:
        mode = "TRUNCATE" if bool(truncate) else "PASSIVE"
        rows: list[dict[str, Any]] = []
        with self._lock:
            with self._connect() as conn:
                try:
                    cur = conn.execute(f"PRAGMA wal_checkpoint({mode});")
                    fetched = cur.fetchall()
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    fetched = []
                conn.commit()
        for item in fetched:
            if isinstance(item, sqlite3.Row):
                rows.append({str(k): item[k] for k in item.keys()})
        return {
            "ok": True,
            "mode": mode,
            "rows": rows,
        }
