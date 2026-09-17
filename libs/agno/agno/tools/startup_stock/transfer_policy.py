"""Transfer restrictions and allowlist policy for startup stock."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TransferPolicy:
    restricted: bool = True
    require_allowlist: bool = True
    lockup_until: Optional[str] = None
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TransferPolicyStore:
    """SQLite-backed transfer allowlist and lockup policy."""

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
                CREATE TABLE IF NOT EXISTS transfer_policy (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    restricted INTEGER NOT NULL DEFAULT 1,
                    require_allowlist INTEGER NOT NULL DEFAULT 1,
                    lockup_until TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transfer_allowlist (
                    wallet_address TEXT PRIMARY KEY,
                    label TEXT,
                    added_at TEXT NOT NULL
                )
                """
            )
            row = conn.execute("SELECT id FROM transfer_policy WHERE id = 1").fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO transfer_policy (id, restricted, require_allowlist, lockup_until, updated_at)
                    VALUES (1, 1, 1, NULL, ?)
                    """,
                    (datetime.now(timezone.utc).isoformat(),),
                )

    def get_policy(self) -> TransferPolicy:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM transfer_policy WHERE id = 1").fetchone()
        return TransferPolicy(
            restricted=bool(row["restricted"]),
            require_allowlist=bool(row["require_allowlist"]),
            lockup_until=row["lockup_until"],
            updated_at=row["updated_at"],
        )

    def update_policy(
        self,
        restricted: Optional[bool] = None,
        require_allowlist: Optional[bool] = None,
        lockup_until: Optional[str] = None,
    ) -> TransferPolicy:
        policy = self.get_policy()
        if restricted is not None:
            policy.restricted = restricted
        if require_allowlist is not None:
            policy.require_allowlist = require_allowlist
        if lockup_until is not None:
            policy.lockup_until = lockup_until or None
        policy.updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE transfer_policy
                SET restricted = ?, require_allowlist = ?, lockup_until = ?, updated_at = ?
                WHERE id = 1
                """,
                (
                    int(policy.restricted),
                    int(policy.require_allowlist),
                    policy.lockup_until,
                    policy.updated_at,
                ),
            )
        return policy

    def add_to_allowlist(self, wallet_address: str, label: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        address = wallet_address.lower()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO transfer_allowlist (wallet_address, label, added_at)
                VALUES (?, ?, ?)
                ON CONFLICT(wallet_address) DO UPDATE SET label = excluded.label
                """,
                (address, label, now),
            )
        return {"wallet_address": address, "label": label, "added_at": now}

    def remove_from_allowlist(self, wallet_address: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM transfer_allowlist WHERE wallet_address = ?",
                (wallet_address.lower(),),
            )
            return cur.rowcount > 0

    def list_allowlist(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT wallet_address, label, added_at FROM transfer_allowlist ORDER BY added_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def is_allowlisted(self, wallet_address: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM transfer_allowlist WHERE wallet_address = ?",
                (wallet_address.lower(),),
            ).fetchone()
        return row is not None

    def check_transfer_allowed(
        self,
        from_address: str,
        to_address: str,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Validate whether a transfer is permitted under current policy."""
        policy = self.get_policy()
        now = now or datetime.now(timezone.utc)
        reasons: List[str] = []

        if not policy.restricted:
            return {"allowed": True, "policy": policy.to_dict(), "reasons": []}

        if policy.lockup_until:
            try:
                lockup_end = datetime.fromisoformat(policy.lockup_until.replace("Z", "+00:00"))
                if now < lockup_end:
                    reasons.append(f"Lockup active until {policy.lockup_until}")
            except ValueError:
                reasons.append(f"Invalid lockup_until value: {policy.lockup_until}")

        if policy.require_allowlist:
            if not self.is_allowlisted(from_address):
                reasons.append(f"Sender not allowlisted: {from_address.lower()}")
            if not self.is_allowlisted(to_address):
                reasons.append(f"Recipient not allowlisted: {to_address.lower()}")

        return {
            "allowed": len(reasons) == 0,
            "policy": policy.to_dict(),
            "from_address": from_address.lower(),
            "to_address": to_address.lower(),
            "reasons": reasons,
        }
