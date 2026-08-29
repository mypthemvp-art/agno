"""Employee option pool management for startup equity."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class OptionGrant:
    grant_id: str
    recipient_name: str
    recipient_wallet: Optional[str]
    shares: float
    strike_price: float
    vested_shares: float = 0.0
    exercised_shares: float = 0.0
    status: str = "outstanding"  # outstanding | exercised | cancelled
    cliff_days: int = 365
    vesting_days: int = 1460
    granted_at: str = ""
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def outstanding_shares(self) -> float:
        if self.status == "cancelled":
            return 0.0
        return max(0.0, self.shares - self.exercised_shares)


class OptionPoolStore:
    """SQLite-backed option pool and grant ledger."""

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
                CREATE TABLE IF NOT EXISTS option_pool (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    authorized_shares REAL NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS option_grants (
                    grant_id TEXT PRIMARY KEY,
                    recipient_name TEXT NOT NULL,
                    recipient_wallet TEXT,
                    shares REAL NOT NULL,
                    strike_price REAL NOT NULL,
                    vested_shares REAL NOT NULL DEFAULT 0,
                    exercised_shares REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    cliff_days INTEGER NOT NULL,
                    vesting_days INTEGER NOT NULL,
                    granted_at TEXT NOT NULL,
                    notes TEXT
                )
                """
            )

    def set_authorized_shares(self, authorized_shares: float) -> Dict[str, Any]:
        if authorized_shares < 0:
            return {"error": "authorized_shares must be >= 0"}
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO option_pool (id, authorized_shares, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    authorized_shares = excluded.authorized_shares,
                    updated_at = excluded.updated_at
                """,
                (authorized_shares, updated_at),
            )
        return self.get_pool_summary()

    def get_authorized_shares(self) -> float:
        with self._connect() as conn:
            row = conn.execute("SELECT authorized_shares FROM option_pool WHERE id = 1").fetchone()
        return float(row["authorized_shares"]) if row else 0.0

    def list_grants(self, status: Optional[str] = None) -> List[OptionGrant]:
        query = "SELECT * FROM option_grants"
        params: list = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY granted_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_grant(row) for row in rows]

    def get_grant(self, grant_id: str) -> Optional[OptionGrant]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM option_grants WHERE grant_id = ?", (grant_id,)).fetchone()
        return self._row_to_grant(row) if row else None

    def grant_options(
        self,
        recipient_name: str,
        shares: float,
        strike_price: float,
        recipient_wallet: Optional[str] = None,
        cliff_days: int = 365,
        vesting_days: int = 1460,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        if shares <= 0:
            return {"error": "shares must be > 0"}
        if strike_price < 0:
            return {"error": "strike_price must be >= 0"}

        summary = self.get_pool_summary()
        available = summary["available_shares"]
        if shares > available:
            return {
                "error": "Insufficient option pool capacity",
                "requested": shares,
                "available": available,
            }

        grant = OptionGrant(
            grant_id=uuid.uuid4().hex[:12],
            recipient_name=recipient_name,
            recipient_wallet=recipient_wallet.lower() if recipient_wallet else None,
            shares=shares,
            strike_price=strike_price,
            cliff_days=cliff_days,
            vesting_days=vesting_days,
            granted_at=datetime.now(timezone.utc).isoformat(),
            notes=notes,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO option_grants (
                    grant_id, recipient_name, recipient_wallet, shares, strike_price,
                    vested_shares, exercised_shares, status, cliff_days, vesting_days,
                    granted_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    grant.grant_id,
                    grant.recipient_name,
                    grant.recipient_wallet,
                    grant.shares,
                    grant.strike_price,
                    grant.vested_shares,
                    grant.exercised_shares,
                    grant.status,
                    grant.cliff_days,
                    grant.vesting_days,
                    grant.granted_at,
                    grant.notes,
                ),
            )
        return {"grant": grant.to_dict(), "pool": self.get_pool_summary()}

    def update_vested_shares(self, grant_id: str, vested_shares: float) -> Dict[str, Any]:
        grant = self.get_grant(grant_id)
        if not grant:
            return {"error": "Grant not found", "grant_id": grant_id}
        if grant.status == "cancelled":
            return {"error": "Cannot update cancelled grant", "grant_id": grant_id}
        if vested_shares < 0 or vested_shares > grant.shares:
            return {"error": "vested_shares must be between 0 and grant shares"}

        with self._connect() as conn:
            conn.execute(
                "UPDATE option_grants SET vested_shares = ? WHERE grant_id = ?",
                (vested_shares, grant_id),
            )
        updated = self.get_grant(grant_id)
        assert updated is not None
        return updated.to_dict()

    def exercise_options(self, grant_id: str, shares: float) -> Dict[str, Any]:
        grant = self.get_grant(grant_id)
        if not grant:
            return {"error": "Grant not found", "grant_id": grant_id}
        if grant.status == "cancelled":
            return {"error": "Cannot exercise cancelled grant", "grant_id": grant_id}
        if shares <= 0:
            return {"error": "shares must be > 0"}

        exercisable = max(0.0, min(grant.vested_shares, grant.outstanding_shares))
        if shares > exercisable:
            return {
                "error": "Insufficient vested/outstanding shares to exercise",
                "requested": shares,
                "exercisable": exercisable,
            }

        new_exercised = grant.exercised_shares + shares
        new_status = "exercised" if new_exercised >= grant.shares else "outstanding"
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE option_grants
                SET exercised_shares = ?, status = ?
                WHERE grant_id = ?
                """,
                (new_exercised, new_status, grant_id),
            )
        updated = self.get_grant(grant_id)
        assert updated is not None
        return {
            "grant": updated.to_dict(),
            "exercised_now": shares,
            "exercise_cost": round(shares * grant.strike_price, 6),
            "pool": self.get_pool_summary(),
        }

    def cancel_grant(self, grant_id: str) -> Dict[str, Any]:
        grant = self.get_grant(grant_id)
        if not grant:
            return {"error": "Grant not found", "grant_id": grant_id}
        with self._connect() as conn:
            conn.execute(
                "UPDATE option_grants SET status = 'cancelled' WHERE grant_id = ?",
                (grant_id,),
            )
        return {"grant_id": grant_id, "status": "cancelled", "pool": self.get_pool_summary()}

    def get_pool_summary(self) -> Dict[str, Any]:
        authorized = self.get_authorized_shares()
        grants = self.list_grants()
        granted = sum(g.outstanding_shares for g in grants if g.status != "cancelled")
        exercised = sum(g.exercised_shares for g in grants)
        cancelled = sum(g.shares for g in grants if g.status == "cancelled")
        available = max(0.0, authorized - granted)
        return {
            "authorized_shares": authorized,
            "granted_outstanding": granted,
            "exercised_shares": exercised,
            "cancelled_shares": cancelled,
            "available_shares": available,
            "utilization_pct": round(100 * granted / authorized, 4) if authorized > 0 else 0.0,
            "grant_count": len([g for g in grants if g.status != "cancelled"]),
        }

    @staticmethod
    def _row_to_grant(row: sqlite3.Row) -> OptionGrant:
        return OptionGrant(
            grant_id=row["grant_id"],
            recipient_name=row["recipient_name"],
            recipient_wallet=row["recipient_wallet"],
            shares=row["shares"],
            strike_price=row["strike_price"],
            vested_shares=row["vested_shares"],
            exercised_shares=row["exercised_shares"],
            status=row["status"],
            cliff_days=row["cliff_days"],
            vesting_days=row["vesting_days"],
            granted_at=row["granted_at"],
            notes=row["notes"],
        )
