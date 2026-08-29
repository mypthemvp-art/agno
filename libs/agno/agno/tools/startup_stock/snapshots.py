"""Cap table point-in-time snapshots for compliance and versioning."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agno.tools.startup_stock.sync import CapTableEntry, CapTableStore, SyncStatus


class CapTableSnapshotStore:
    """SQLite-backed cap table snapshot history."""

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
                CREATE TABLE IF NOT EXISTS cap_table_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    investor_count INTEGER NOT NULL,
                    total_shares REAL NOT NULL,
                    entries_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def create_snapshot(self, store: CapTableStore, label: str) -> Dict[str, Any]:
        entries = store.list_entries()
        total_shares = sum(e.shares for e in entries)
        snapshot_id = uuid.uuid4().hex[:12]
        created_at = datetime.now(timezone.utc).isoformat()
        entries_data = [self._entry_to_dict(e) for e in entries]

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cap_table_snapshots
                (snapshot_id, label, investor_count, total_shares, entries_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    label,
                    len(entries),
                    total_shares,
                    json.dumps(entries_data),
                    created_at,
                ),
            )

        return {
            "snapshot_id": snapshot_id,
            "label": label,
            "investor_count": len(entries),
            "total_shares": total_shares,
            "created_at": created_at,
        }

    def list_snapshots(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT snapshot_id, label, investor_count, total_shares, created_at
                FROM cap_table_snapshots
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM cap_table_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "snapshot_id": row["snapshot_id"],
            "label": row["label"],
            "investor_count": row["investor_count"],
            "total_shares": row["total_shares"],
            "created_at": row["created_at"],
            "entries": json.loads(row["entries_json"]),
        }

    def compare_snapshots(self, snapshot_id_a: str, snapshot_id_b: str) -> Dict[str, Any]:
        snap_a = self.get_snapshot(snapshot_id_a)
        snap_b = self.get_snapshot(snapshot_id_b)
        if not snap_a or not snap_b:
            return {"error": "One or both snapshots not found"}

        map_a = {e["wallet_address"]: e for e in snap_a["entries"]}
        map_b = {e["wallet_address"]: e for e in snap_b["entries"]}
        all_wallets = set(map_a) | set(map_b)

        added: List[Dict[str, Any]] = []
        removed: List[Dict[str, Any]] = []
        changed: List[Dict[str, Any]] = []

        for wallet in sorted(all_wallets):
            in_a = wallet in map_a
            in_b = wallet in map_b
            if in_a and not in_b:
                removed.append(map_a[wallet])
            elif in_b and not in_a:
                added.append(map_b[wallet])
            elif map_a[wallet]["shares"] != map_b[wallet]["shares"]:
                changed.append(
                    {
                        "wallet_address": wallet,
                        "investor_name": map_b[wallet]["investor_name"],
                        "shares_before": map_a[wallet]["shares"],
                        "shares_after": map_b[wallet]["shares"],
                        "delta": map_b[wallet]["shares"] - map_a[wallet]["shares"],
                    }
                )

        return {
            "snapshot_a": snapshot_id_a,
            "snapshot_b": snapshot_id_b,
            "label_a": snap_a["label"],
            "label_b": snap_b["label"],
            "added": added,
            "removed": removed,
            "changed": changed,
            "total_shares_before": snap_a["total_shares"],
            "total_shares_after": snap_b["total_shares"],
            "total_shares_delta": snap_b["total_shares"] - snap_a["total_shares"],
        }

    @staticmethod
    def _entry_to_dict(entry: CapTableEntry) -> Dict[str, Any]:
        data = asdict(entry)
        if isinstance(entry.status, SyncStatus):
            data["status"] = entry.status.value
        return data
