"""Cap table sync engine for startup stock tokenization."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol


class SyncStatus(str, Enum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
    DRIFT = "drift"


@dataclass
class CapTableEntry:
    investor_name: str
    wallet_address: str
    shares: float
    status: SyncStatus = SyncStatus.PENDING
    checksum: str = ""
    last_synced_at: Optional[str] = None
    last_tx_hash: Optional[str] = None
    error: Optional[str] = None

    def compute_checksum(self) -> str:
        payload = f"{self.investor_name}:{self.wallet_address.lower()}:{self.shares:.18f}"
        return hashlib.sha256(payload.encode()).hexdigest()


class OnChainReader(Protocol):
    def get_balance(self, wallet_address: str) -> int: ...


class OnChainMinter(Protocol):
    def mint_shares_wei(self, wallet_address: str, amount_wei: int) -> str: ...


class CapTableStore:
    """SQLite-backed cap table for fast local sync state."""

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
                CREATE TABLE IF NOT EXISTS cap_table (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    investor_name TEXT NOT NULL,
                    wallet_address TEXT NOT NULL UNIQUE,
                    shares REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    checksum TEXT NOT NULL,
                    last_synced_at TEXT,
                    last_tx_hash TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    wallet_address TEXT,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

    def upsert_entry(self, entry: CapTableEntry) -> None:
        entry.checksum = entry.compute_checksum()
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cap_table (
                    investor_name, wallet_address, shares, status, checksum,
                    last_synced_at, last_tx_hash, error, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(wallet_address) DO UPDATE SET
                    investor_name = excluded.investor_name,
                    shares = excluded.shares,
                    status = excluded.status,
                    checksum = excluded.checksum,
                    last_synced_at = excluded.last_synced_at,
                    last_tx_hash = excluded.last_tx_hash,
                    error = excluded.error,
                    updated_at = excluded.updated_at
                """,
                (
                    entry.investor_name,
                    entry.wallet_address.lower(),
                    entry.shares,
                    entry.status.value,
                    entry.checksum,
                    entry.last_synced_at,
                    entry.last_tx_hash,
                    entry.error,
                    now,
                ),
            )

    def list_entries(self) -> List[CapTableEntry]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM cap_table ORDER BY investor_name").fetchall()
        return [self._row_to_entry(row) for row in rows]

    def get_entry(self, wallet_address: str) -> Optional[CapTableEntry]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM cap_table WHERE wallet_address = ?",
                (wallet_address.lower(),),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def log_sync_event(
        self,
        run_id: str,
        action: str,
        status: str,
        wallet_address: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_log (run_id, wallet_address, action, status, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    wallet_address.lower() if wallet_address else None,
                    action,
                    status,
                    detail,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> CapTableEntry:
        return CapTableEntry(
            investor_name=row["investor_name"],
            wallet_address=row["wallet_address"],
            shares=row["shares"],
            status=SyncStatus(row["status"]),
            checksum=row["checksum"],
            last_synced_at=row["last_synced_at"],
            last_tx_hash=row["last_tx_hash"],
            error=row["error"],
        )


@dataclass
class SyncResult:
    run_id: str
    synced: int
    failed: int
    drifted: int
    skipped: int
    entries: List[Dict[str, Any]]


class CapTableSyncEngine:
    """Fast, retryable off-chain to on-chain cap table sync."""

    def __init__(
        self,
        store: CapTableStore,
        on_chain_reader: OnChainReader,
        on_chain_minter: OnChainMinter,
        shares_to_wei: Callable[[float], int],
        wei_to_shares: Callable[[int], float],
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
    ):
        self.store = store
        self.on_chain_reader = on_chain_reader
        self.on_chain_minter = on_chain_minter
        self.shares_to_wei = shares_to_wei
        self.wei_to_shares = wei_to_shares
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def add_investor(self, investor_name: str, wallet_address: str, shares: float) -> CapTableEntry:
        if shares <= 0:
            raise ValueError("Shares must be positive")
        if not wallet_address.startswith("0x") or len(wallet_address) != 42:
            raise ValueError("Invalid wallet address")
        entry = CapTableEntry(
            investor_name=investor_name,
            wallet_address=wallet_address.lower(),
            shares=shares,
            status=SyncStatus.PENDING,
        )
        self.store.upsert_entry(entry)
        return entry

    def sync_all(self, dry_run: bool = False) -> SyncResult:
        run_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
        synced = failed = drifted = skipped = 0
        results: List[Dict[str, Any]] = []

        for entry in self.store.list_entries():
            outcome = self._sync_entry(entry, run_id=run_id, dry_run=dry_run)
            results.append(outcome)
            status = outcome["status"]
            if status == SyncStatus.SYNCED.value:
                synced += 1
            elif status == SyncStatus.FAILED.value:
                failed += 1
            elif status == SyncStatus.DRIFT.value:
                drifted += 1
            else:
                skipped += 1

        self.store.log_sync_event(
            run_id=run_id,
            action="sync_all",
            status="completed",
            detail=json.dumps({"synced": synced, "failed": failed, "drifted": drifted, "skipped": skipped}),
        )
        return SyncResult(
            run_id=run_id,
            synced=synced,
            failed=failed,
            drifted=drifted,
            skipped=skipped,
            entries=results,
        )

    def _sync_entry(self, entry: CapTableEntry, run_id: str, dry_run: bool) -> Dict[str, Any]:
        target_wei = self.shares_to_wei(entry.shares)
        try:
            on_chain_wei = self.on_chain_reader.get_balance(entry.wallet_address)
        except Exception as e:
            entry.status = SyncStatus.FAILED
            entry.error = str(e)
            self.store.upsert_entry(entry)
            self.store.log_sync_event(run_id, "read_balance", "failed", entry.wallet_address, str(e))
            return asdict(entry) | {"status": SyncStatus.FAILED.value}

        on_chain_shares = self.wei_to_shares(on_chain_wei)
        delta_wei = target_wei - on_chain_wei

        if delta_wei == 0:
            entry.status = SyncStatus.SYNCED
            entry.error = None
            entry.last_synced_at = datetime.now(timezone.utc).isoformat()
            self.store.upsert_entry(entry)
            self.store.log_sync_event(run_id, "noop", "synced", entry.wallet_address)
            return asdict(entry) | {"status": SyncStatus.SYNCED.value, "on_chain_shares": on_chain_shares}

        if delta_wei < 0:
            entry.status = SyncStatus.DRIFT
            entry.error = "On-chain balance exceeds cap table; manual review required"
            self.store.upsert_entry(entry)
            self.store.log_sync_event(run_id, "drift", "drift", entry.wallet_address, entry.error)
            return asdict(entry) | {"status": SyncStatus.DRIFT.value, "on_chain_shares": on_chain_shares}

        if dry_run:
            self.store.log_sync_event(
                run_id,
                "mint",
                "dry_run",
                entry.wallet_address,
                f"would_mint_wei={delta_wei}",
            )
            return asdict(entry) | {
                "status": SyncStatus.PENDING.value,
                "on_chain_shares": on_chain_shares,
                "mint_delta_wei": delta_wei,
            }

        tx_hash = self._mint_with_retry(entry.wallet_address, delta_wei, run_id)
        if tx_hash.startswith("error:"):
            entry.status = SyncStatus.FAILED
            entry.error = tx_hash
            self.store.upsert_entry(entry)
            return asdict(entry) | {"status": SyncStatus.FAILED.value, "on_chain_shares": on_chain_shares}

        entry.status = SyncStatus.SYNCED
        entry.error = None
        entry.last_tx_hash = tx_hash
        entry.last_synced_at = datetime.now(timezone.utc).isoformat()
        self.store.upsert_entry(entry)
        self.store.log_sync_event(run_id, "mint", "synced", entry.wallet_address, tx_hash)
        return asdict(entry) | {
            "status": SyncStatus.SYNCED.value,
            "on_chain_shares": on_chain_shares,
            "tx_hash": tx_hash,
        }

    def _mint_with_retry(self, wallet_address: str, amount_wei: int, run_id: str) -> str:
        last_error = "unknown error"
        for attempt in range(1, self.max_retries + 1):
            try:
                tx_hash = self.on_chain_minter.mint_shares_wei(wallet_address, amount_wei)
                if not tx_hash.startswith("error:"):
                    return tx_hash
                last_error = tx_hash
            except Exception as e:
                last_error = f"error: {e}"
            self.store.log_sync_event(
                run_id,
                "mint_retry",
                "failed",
                wallet_address,
                f"attempt={attempt} error={last_error}",
            )
            if attempt < self.max_retries:
                time.sleep(self.retry_delay_seconds * attempt)
        return last_error
