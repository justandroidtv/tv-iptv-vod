from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ControlPlaneDB:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    action TEXT NOT NULL,
                    scope TEXT,
                    state TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_updated ON jobs(updated_at DESC);

                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_at ON audit(at DESC);
                """
            )

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_job(self, task_id: str, action: str, scope: str | None, payload: dict[str, Any]) -> None:
        now = self.now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs(task_id, action, scope, state, payload_json, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (task_id, action, scope, "queued", json.dumps(payload, ensure_ascii=False), now, now),
            )

    def update_job(self, task_id: str, state: str, result: dict[str, Any] | None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET state=?, result_json=?, updated_at=?
                WHERE task_id=?
                """,
                (
                    state,
                    json.dumps(result, ensure_ascii=False, default=str) if result is not None else None,
                    self.now(),
                    task_id,
                ),
            )

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(200, int(limit)))
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_job(self, task_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE task_id=?", (task_id,)
            ).fetchone()
        return dict(row) if row else None

    def audit(self, actor: str, action: str, details: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO audit(at, actor, action, details_json) VALUES(?,?,?,?)",
                (self.now(), actor, action, json.dumps(details, ensure_ascii=False, default=str)),
            )

    def tail_audit(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(200, int(limit)))
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit ORDER BY at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
