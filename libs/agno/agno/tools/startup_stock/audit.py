"""Audit trail for startup stock operations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AuditEvent:
    action: str
    actor: str
    target: Optional[str] = None
    detail: Optional[str] = None
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AuditStore:
    """SQLite-backed audit log for compliance and traceability."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    target TEXT,
                    detail TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

    def record(
        self,
        action: str,
        actor: str,
        target: Optional[str] = None,
        detail: Optional[Any] = None,
    ) -> AuditEvent:
        created_at = datetime.now(timezone.utc).isoformat()
        detail_str = json.dumps(detail, default=str) if detail is not None else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (action, actor, target, detail, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (action, actor, target, detail_str, created_at),
            )
        return AuditEvent(
            action=action,
            actor=actor,
            target=target,
            detail=detail_str,
            created_at=created_at,
        )

    def list_events(self, limit: int = 50, action: Optional[str] = None) -> List[AuditEvent]:
        query = "SELECT * FROM audit_log"
        params: list = []
        if action:
            query += " WHERE action = ?"
            params.append(action)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            AuditEvent(
                action=row["action"],
                actor=row["actor"],
                target=row["target"],
                detail=row["detail"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
