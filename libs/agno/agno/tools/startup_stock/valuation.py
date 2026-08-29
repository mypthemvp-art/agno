"""409A fair market value valuation helpers for startup equity."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Valuation409A:
    valuation_id: str
    fair_market_value: float
    valuation_date: str
    firm: str
    methodology: str = "market_approach"
    share_class: str = "common"
    expires_at: Optional[str] = None
    notes: Optional[str] = None
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Valuation409AStore:
    """SQLite-backed 409A valuation history."""

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
                CREATE TABLE IF NOT EXISTS valuations_409a (
                    valuation_id TEXT PRIMARY KEY,
                    fair_market_value REAL NOT NULL,
                    valuation_date TEXT NOT NULL,
                    firm TEXT NOT NULL,
                    methodology TEXT NOT NULL,
                    share_class TEXT NOT NULL,
                    expires_at TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

    def record_valuation(
        self,
        fair_market_value: float,
        firm: str,
        valuation_date: Optional[str] = None,
        methodology: str = "market_approach",
        share_class: str = "common",
        validity_days: int = 365,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        if fair_market_value < 0:
            return {"error": "fair_market_value must be >= 0"}
        if not firm.strip():
            return {"error": "firm is required"}

        created_at = datetime.now(timezone.utc)
        v_date = valuation_date or created_at.date().isoformat()
        try:
            base_date = datetime.fromisoformat(v_date.replace("Z", "+00:00"))
            if base_date.tzinfo is None:
                base_date = base_date.replace(tzinfo=timezone.utc)
        except ValueError:
            base_date = created_at

        expires_at = (base_date + timedelta(days=validity_days)).date().isoformat()
        valuation = Valuation409A(
            valuation_id=uuid.uuid4().hex[:12],
            fair_market_value=fair_market_value,
            valuation_date=v_date,
            firm=firm,
            methodology=methodology,
            share_class=share_class,
            expires_at=expires_at,
            notes=notes,
            created_at=created_at.isoformat(),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO valuations_409a (
                    valuation_id, fair_market_value, valuation_date, firm,
                    methodology, share_class, expires_at, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    valuation.valuation_id,
                    valuation.fair_market_value,
                    valuation.valuation_date,
                    valuation.firm,
                    valuation.methodology,
                    valuation.share_class,
                    valuation.expires_at,
                    valuation.notes,
                    valuation.created_at,
                ),
            )
        return valuation.to_dict()

    def list_valuations(self, limit: int = 20) -> List[Valuation409A]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM valuations_409a
                ORDER BY valuation_date DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_valuation(row) for row in rows]

    def get_latest(self, share_class: str = "common") -> Optional[Valuation409A]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM valuations_409a
                WHERE share_class = ?
                ORDER BY valuation_date DESC, created_at DESC
                LIMIT 1
                """,
                (share_class,),
            ).fetchone()
        return self._row_to_valuation(row) if row else None

    def is_current(self, share_class: str = "common", as_of: Optional[str] = None) -> Dict[str, Any]:
        latest = self.get_latest(share_class=share_class)
        if not latest:
            return {
                "current": False,
                "reason": "No 409A valuation on file",
                "share_class": share_class,
            }

        as_of_date = as_of or datetime.now(timezone.utc).date().isoformat()
        expired = bool(latest.expires_at and as_of_date > latest.expires_at)
        return {
            "current": not expired,
            "reason": "expired" if expired else "valid",
            "as_of": as_of_date,
            "valuation": latest.to_dict(),
        }

    @staticmethod
    def _row_to_valuation(row: sqlite3.Row) -> Valuation409A:
        return Valuation409A(
            valuation_id=row["valuation_id"],
            fair_market_value=row["fair_market_value"],
            valuation_date=row["valuation_date"],
            firm=row["firm"],
            methodology=row["methodology"],
            share_class=row["share_class"],
            expires_at=row["expires_at"],
            notes=row["notes"],
            created_at=row["created_at"],
        )


def compute_option_intrinsic_value(
    fair_market_value: float,
    strike_price: float,
    shares: float,
) -> Dict[str, Any]:
    """Compute intrinsic value of options under a 409A FMV."""
    if shares < 0:
        return {"error": "shares must be >= 0"}
    spread = fair_market_value - strike_price
    intrinsic_per_share = max(0.0, spread)
    return {
        "fair_market_value": fair_market_value,
        "strike_price": strike_price,
        "shares": shares,
        "intrinsic_per_share": round(intrinsic_per_share, 6),
        "intrinsic_value": round(intrinsic_per_share * shares, 6),
        "in_the_money": spread > 0,
    }


def suggest_strike_from_409a(
    fair_market_value: float,
    discount_pct: float = 0.0,
) -> Dict[str, Any]:
    """Suggest an option strike price from 409A FMV (typically at FMV)."""
    if fair_market_value < 0:
        return {"error": "fair_market_value must be >= 0"}
    if discount_pct < 0 or discount_pct >= 100:
        return {"error": "discount_pct must be in [0, 100)"}
    suggested = fair_market_value * (1 - discount_pct / 100.0)
    return {
        "fair_market_value": fair_market_value,
        "discount_pct": discount_pct,
        "suggested_strike": round(suggested, 6),
        "note": "ISO-compliant grants typically set strike equal to current 409A FMV",
    }
