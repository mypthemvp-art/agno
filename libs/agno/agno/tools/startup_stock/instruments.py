"""SAFE and SAFT instrument tracking with conversion modeling."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VALID_INSTRUMENT_TYPES = {"safe", "saft"}
VALID_STATUSES = {"outstanding", "converted", "cancelled"}


@dataclass
class EquityInstrument:
    instrument_id: str
    investor_name: str
    instrument_type: str  # safe | saft
    investment_amount: float
    valuation_cap: Optional[float] = None
    discount_rate: float = 0.0  # e.g. 0.20 for 20%
    status: str = "outstanding"
    issued_at: str = ""
    converted_shares: Optional[float] = None
    conversion_price: Optional[float] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class InstrumentStore:
    """SQLite-backed SAFE/SAFT instrument ledger."""

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
                CREATE TABLE IF NOT EXISTS equity_instruments (
                    instrument_id TEXT PRIMARY KEY,
                    investor_name TEXT NOT NULL,
                    instrument_type TEXT NOT NULL,
                    investment_amount REAL NOT NULL,
                    valuation_cap REAL,
                    discount_rate REAL NOT NULL,
                    status TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    converted_shares REAL,
                    conversion_price REAL,
                    notes TEXT
                )
                """
            )

    def add_instrument(
        self,
        investor_name: str,
        instrument_type: str,
        investment_amount: float,
        valuation_cap: Optional[float] = None,
        discount_rate: float = 0.0,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        instrument_type = instrument_type.lower().strip()
        if instrument_type not in VALID_INSTRUMENT_TYPES:
            return {"error": f"instrument_type must be one of {sorted(VALID_INSTRUMENT_TYPES)}"}
        if investment_amount <= 0:
            return {"error": "investment_amount must be > 0"}
        if discount_rate < 0 or discount_rate >= 1:
            return {"error": "discount_rate must be in [0, 1)"}
        if valuation_cap is not None and valuation_cap <= 0:
            return {"error": "valuation_cap must be > 0 when provided"}

        instrument = EquityInstrument(
            instrument_id=uuid.uuid4().hex[:12],
            investor_name=investor_name,
            instrument_type=instrument_type,
            investment_amount=investment_amount,
            valuation_cap=valuation_cap,
            discount_rate=discount_rate,
            issued_at=datetime.now(timezone.utc).isoformat(),
            notes=notes,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO equity_instruments (
                    instrument_id, investor_name, instrument_type, investment_amount,
                    valuation_cap, discount_rate, status, issued_at, converted_shares,
                    conversion_price, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    instrument.instrument_id,
                    instrument.investor_name,
                    instrument.instrument_type,
                    instrument.investment_amount,
                    instrument.valuation_cap,
                    instrument.discount_rate,
                    instrument.status,
                    instrument.issued_at,
                    instrument.converted_shares,
                    instrument.conversion_price,
                    instrument.notes,
                ),
            )
        return instrument.to_dict()

    def list_instruments(self, status: Optional[str] = None) -> List[EquityInstrument]:
        query = "SELECT * FROM equity_instruments"
        params: list = []
        if status:
            if status not in VALID_STATUSES:
                return []
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY issued_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_instrument(row) for row in rows]

    def get_instrument(self, instrument_id: str) -> Optional[EquityInstrument]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM equity_instruments WHERE instrument_id = ?",
                (instrument_id,),
            ).fetchone()
        return self._row_to_instrument(row) if row else None

    def cancel_instrument(self, instrument_id: str) -> Dict[str, Any]:
        instrument = self.get_instrument(instrument_id)
        if not instrument:
            return {"error": "Instrument not found", "instrument_id": instrument_id}
        if instrument.status != "outstanding":
            return {"error": f"Cannot cancel instrument in status {instrument.status}"}
        with self._connect() as conn:
            conn.execute(
                "UPDATE equity_instruments SET status = 'cancelled' WHERE instrument_id = ?",
                (instrument_id,),
            )
        return {"instrument_id": instrument_id, "status": "cancelled"}

    def mark_converted(
        self,
        instrument_id: str,
        converted_shares: float,
        conversion_price: float,
    ) -> Dict[str, Any]:
        instrument = self.get_instrument(instrument_id)
        if not instrument:
            return {"error": "Instrument not found", "instrument_id": instrument_id}
        if instrument.status != "outstanding":
            return {"error": f"Cannot convert instrument in status {instrument.status}"}
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE equity_instruments
                SET status = 'converted', converted_shares = ?, conversion_price = ?
                WHERE instrument_id = ?
                """,
                (converted_shares, conversion_price, instrument_id),
            )
        updated = self.get_instrument(instrument_id)
        assert updated is not None
        return updated.to_dict()

    def summary(self) -> Dict[str, Any]:
        instruments = self.list_instruments()
        outstanding = [i for i in instruments if i.status == "outstanding"]
        return {
            "total_instruments": len(instruments),
            "outstanding_count": len(outstanding),
            "outstanding_amount": sum(i.investment_amount for i in outstanding),
            "converted_count": len([i for i in instruments if i.status == "converted"]),
            "cancelled_count": len([i for i in instruments if i.status == "cancelled"]),
            "by_type": {
                "safe": len([i for i in instruments if i.instrument_type == "safe"]),
                "saft": len([i for i in instruments if i.instrument_type == "saft"]),
            },
        }

    @staticmethod
    def _row_to_instrument(row: sqlite3.Row) -> EquityInstrument:
        return EquityInstrument(
            instrument_id=row["instrument_id"],
            investor_name=row["investor_name"],
            instrument_type=row["instrument_type"],
            investment_amount=row["investment_amount"],
            valuation_cap=row["valuation_cap"],
            discount_rate=row["discount_rate"],
            status=row["status"],
            issued_at=row["issued_at"],
            converted_shares=row["converted_shares"],
            conversion_price=row["conversion_price"],
            notes=row["notes"],
        )


def convert_safe(
    investment_amount: float,
    priced_round_price_per_share: float,
    pre_money_shares: float,
    valuation_cap: Optional[float] = None,
    discount_rate: float = 0.0,
) -> Dict[str, Any]:
    """Model SAFE conversion into shares at a priced equity round.

    Conversion price is the minimum of:
    - discounted round price: priced_round_price * (1 - discount_rate)
    - cap price: valuation_cap / pre_money_shares (when cap is set)
    """
    if investment_amount <= 0:
        return {"error": "investment_amount must be > 0"}
    if priced_round_price_per_share <= 0:
        return {"error": "priced_round_price_per_share must be > 0"}
    if pre_money_shares <= 0:
        return {"error": "pre_money_shares must be > 0"}
    if discount_rate < 0 or discount_rate >= 1:
        return {"error": "discount_rate must be in [0, 1)"}
    if valuation_cap is not None and valuation_cap <= 0:
        return {"error": "valuation_cap must be > 0 when provided"}

    discounted_price = priced_round_price_per_share * (1 - discount_rate)
    candidates = [("discount", discounted_price)]
    if valuation_cap is not None:
        cap_price = valuation_cap / pre_money_shares
        candidates.append(("valuation_cap", cap_price))

    method, conversion_price = min(candidates, key=lambda x: x[1])
    if conversion_price <= 0:
        return {"error": "Computed conversion price must be > 0"}

    shares = investment_amount / conversion_price
    return {
        "investment_amount": investment_amount,
        "priced_round_price_per_share": priced_round_price_per_share,
        "pre_money_shares": pre_money_shares,
        "valuation_cap": valuation_cap,
        "discount_rate": discount_rate,
        "conversion_method": method,
        "conversion_price": round(conversion_price, 8),
        "converted_shares": round(shares, 6),
        "ownership_pct_pre_round": round(100 * shares / (pre_money_shares + shares), 4),
    }


def preview_instrument_conversion(
    instrument: EquityInstrument,
    priced_round_price_per_share: float,
    pre_money_shares: float,
) -> Dict[str, Any]:
    """Preview conversion for a stored SAFE/SAFT instrument."""
    result = convert_safe(
        investment_amount=instrument.investment_amount,
        priced_round_price_per_share=priced_round_price_per_share,
        pre_money_shares=pre_money_shares,
        valuation_cap=instrument.valuation_cap,
        discount_rate=instrument.discount_rate,
    )
    if "error" in result:
        return result
    result["instrument_id"] = instrument.instrument_id
    result["investor_name"] = instrument.investor_name
    result["instrument_type"] = instrument.instrument_type
    return result
