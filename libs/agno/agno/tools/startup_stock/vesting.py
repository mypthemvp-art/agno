"""Vesting schedule management for startup equity."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agno.tools.startup_stock.base import shares_to_wei, wei_to_shares
from agno.tools.startup_stock.contracts.extended_abi import VESTING_VAULT_ABI

try:
    from web3 import Web3
except ImportError:
    raise ImportError("`web3` not installed. Please install using `pip install agno[evm]`")


@dataclass
class VestingSchedule:
    beneficiary: str
    total_shares: float
    start_timestamp: int
    cliff_seconds: int
    vesting_seconds: int
    released_shares: float = 0.0
    revoked: bool = False
    vault_address: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VestingStore:
    """SQLite store for off-chain vesting schedule tracking."""

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
                CREATE TABLE IF NOT EXISTS vesting_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    beneficiary TEXT NOT NULL UNIQUE,
                    total_shares REAL NOT NULL,
                    start_timestamp INTEGER NOT NULL,
                    cliff_seconds INTEGER NOT NULL,
                    vesting_seconds INTEGER NOT NULL,
                    released_shares REAL NOT NULL DEFAULT 0,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    vault_address TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def upsert(self, schedule: VestingSchedule) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO vesting_schedules (
                    beneficiary, total_shares, start_timestamp, cliff_seconds,
                    vesting_seconds, released_shares, revoked, vault_address, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(beneficiary) DO UPDATE SET
                    total_shares = excluded.total_shares,
                    start_timestamp = excluded.start_timestamp,
                    cliff_seconds = excluded.cliff_seconds,
                    vesting_seconds = excluded.vesting_seconds,
                    released_shares = excluded.released_shares,
                    revoked = excluded.revoked,
                    vault_address = excluded.vault_address,
                    updated_at = excluded.updated_at
                """,
                (
                    schedule.beneficiary.lower(),
                    schedule.total_shares,
                    schedule.start_timestamp,
                    schedule.cliff_seconds,
                    schedule.vesting_seconds,
                    schedule.released_shares,
                    1 if schedule.revoked else 0,
                    schedule.vault_address,
                    now,
                ),
            )

    def list_schedules(self) -> List[VestingSchedule]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM vesting_schedules ORDER BY beneficiary").fetchall()
        return [self._row_to_schedule(row) for row in rows]

    def get(self, beneficiary: str) -> Optional[VestingSchedule]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM vesting_schedules WHERE beneficiary = ?",
                (beneficiary.lower(),),
            ).fetchone()
        return self._row_to_schedule(row) if row else None

    @staticmethod
    def _row_to_schedule(row: sqlite3.Row) -> VestingSchedule:
        return VestingSchedule(
            beneficiary=row["beneficiary"],
            total_shares=row["total_shares"],
            start_timestamp=row["start_timestamp"],
            cliff_seconds=row["cliff_seconds"],
            vesting_seconds=row["vesting_seconds"],
            released_shares=row["released_shares"],
            revoked=bool(row["revoked"]),
            vault_address=row["vault_address"],
        )


def compute_vested_shares(schedule: VestingSchedule, now: Optional[int] = None) -> float:
    """Compute vested shares for a schedule at a given timestamp."""
    if schedule.revoked:
        return schedule.released_shares
    now_ts = now if now is not None else int(time.time())
    if now_ts < schedule.start_timestamp + schedule.cliff_seconds:
        return 0.0
    if now_ts >= schedule.start_timestamp + schedule.cliff_seconds + schedule.vesting_seconds:
        return schedule.total_shares
    elapsed = now_ts - schedule.start_timestamp - schedule.cliff_seconds
    return schedule.total_shares * elapsed / schedule.vesting_seconds


def compute_releasable_shares(schedule: VestingSchedule, now: Optional[int] = None) -> float:
    vested = compute_vested_shares(schedule, now)
    return max(0.0, vested - schedule.released_shares)


class VestingManager:
    """Manages vesting schedules locally and on-chain via VestingVault."""

    def __init__(self, web3_client, account, private_key: str, vault_address: Optional[str] = None):
        self.web3_client = web3_client
        self.account = account
        self.private_key = private_key
        self.vault_address = vault_address
        self.vault = None
        if vault_address:
            self.vault = web3_client.eth.contract(
                address=Web3.to_checksum_address(vault_address),
                abi=VESTING_VAULT_ABI,
            )

    def set_vault_address(self, vault_address: str) -> None:
        self.vault_address = vault_address
        self.vault = self.web3_client.eth.contract(
            address=Web3.to_checksum_address(vault_address),
            abi=VESTING_VAULT_ABI,
        )

    def get_schedule_on_chain(self, beneficiary: str) -> Dict[str, Any]:
        if not self.vault:
            raise ValueError("Vesting vault address not configured")
        checksum = Web3.to_checksum_address(beneficiary)
        s = self.vault.functions.schedules(checksum).call()
        releasable_wei = int(self.vault.functions.releasable(checksum).call())
        vested_wei = int(self.vault.functions.vestedAmount(checksum).call())
        return {
            "beneficiary": beneficiary.lower(),
            "total_shares": wei_to_shares(s[0]),
            "released_shares": wei_to_shares(s[1]),
            "start_timestamp": s[2],
            "cliff_seconds": s[3],
            "vesting_seconds": s[4],
            "revoked": s[5],
            "vested_shares": wei_to_shares(vested_wei),
            "releasable_shares": wei_to_shares(releasable_wei),
            "vault_address": self.vault_address,
        }

    def create_schedule_on_chain(
        self,
        beneficiary: str,
        total_shares: float,
        start_timestamp: int,
        cliff_seconds: int,
        vesting_seconds: int,
        send_tx_fn,
    ) -> str:
        if not self.vault:
            raise ValueError("Vesting vault address not configured")
        return send_tx_fn(
            self.vault.functions.createSchedule(
                Web3.to_checksum_address(beneficiary),
                shares_to_wei(total_shares),
                start_timestamp,
                cliff_seconds,
                vesting_seconds,
            )
        )

    def release_on_chain(self, beneficiary: str, send_tx_fn) -> str:
        if not self.vault:
            raise ValueError("Vesting vault address not configured")
        return send_tx_fn(self.vault.functions.release(Web3.to_checksum_address(beneficiary)))

    @staticmethod
    def to_json(payload: Dict[str, Any]) -> str:
        return json.dumps(payload, default=str)
