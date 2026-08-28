"""Cap table import and on-chain reconciliation utilities."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Protocol

from agno.tools.startup_stock.sync import CapTableEntry, CapTableStore, SyncStatus


class BalanceReader(Protocol):
    def get_balance(self, wallet_address: str) -> int: ...


def parse_cap_table_csv(file_path: str) -> List[Dict[str, Any]]:
    """Parse a CSV cap table with columns: investor_name, wallet_address, shares."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Cap table file not found: {file_path}")

    rows: List[Dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"investor_name", "wallet_address", "shares"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV must include columns: {', '.join(sorted(required))}")

        for index, row in enumerate(reader, start=2):
            name = (row.get("investor_name") or "").strip()
            wallet = (row.get("wallet_address") or "").strip()
            shares_raw = (row.get("shares") or "").strip()
            if not name or not wallet or not shares_raw:
                raise ValueError(f"Row {index}: investor_name, wallet_address, and shares are required")
            try:
                shares = float(shares_raw)
            except ValueError as e:
                raise ValueError(f"Row {index}: invalid shares value '{shares_raw}'") from e
            if shares <= 0:
                raise ValueError(f"Row {index}: shares must be positive")
            if not wallet.startswith("0x") or len(wallet) != 42:
                raise ValueError(f"Row {index}: invalid wallet address '{wallet}'")
            rows.append({"investor_name": name, "wallet_address": wallet.lower(), "shares": shares})
    return rows


def parse_cap_table_json(file_path: str) -> List[Dict[str, Any]]:
    """Parse a JSON cap table as a list of investor objects."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Cap table file not found: {file_path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "entries" in data:
        data = data["entries"]
    if not isinstance(data, list):
        raise ValueError("JSON cap table must be a list or an object with an 'entries' list")

    rows: List[Dict[str, Any]] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Entry {index}: expected an object")
        name = str(item.get("investor_name", "")).strip()
        wallet = str(item.get("wallet_address", "")).strip().lower()
        shares = item.get("shares")
        if not name or not wallet or shares is None:
            raise ValueError(f"Entry {index}: investor_name, wallet_address, and shares are required")
        shares = float(shares)
        if shares <= 0:
            raise ValueError(f"Entry {index}: shares must be positive")
        if not wallet.startswith("0x") or len(wallet) != 42:
            raise ValueError(f"Entry {index}: invalid wallet address '{wallet}'")
        rows.append({"investor_name": name, "wallet_address": wallet, "shares": shares})
    return rows


def import_cap_table_file(file_path: str) -> List[Dict[str, Any]]:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".csv":
        return parse_cap_table_csv(file_path)
    if suffix == ".json":
        return parse_cap_table_json(file_path)
    raise ValueError("Cap table file must be .csv or .json")


def import_cap_table_to_store(store: CapTableStore, file_path: str) -> Dict[str, Any]:
    rows = import_cap_table_file(file_path)
    imported = 0
    for row in rows:
        entry = CapTableEntry(
            investor_name=row["investor_name"],
            wallet_address=row["wallet_address"],
            shares=row["shares"],
            status=SyncStatus.PENDING,
        )
        store.upsert_entry(entry)
        imported += 1
    return {"imported": imported, "file_path": file_path}


def reconcile_cap_table(
    store: CapTableStore,
    on_chain_reader: BalanceReader,
    shares_to_wei: Callable[[float], int],
    tolerance_wei: int = 0,
) -> Dict[str, Any]:
    """Update local cap table statuses from on-chain balances."""
    synced = drifted = pending = failed = 0
    entries_out: List[Dict[str, Any]] = []

    for entry in store.list_entries():
        try:
            on_chain_wei = on_chain_reader.get_balance(entry.wallet_address)
            target_wei = shares_to_wei(entry.shares)
            delta = on_chain_wei - target_wei

            if delta == 0 or abs(delta) <= tolerance_wei:
                entry.status = SyncStatus.SYNCED
                entry.error = None
                synced += 1
            elif on_chain_wei > target_wei:
                entry.status = SyncStatus.DRIFT
                entry.error = "On-chain balance exceeds cap table"
                drifted += 1
            else:
                entry.status = SyncStatus.PENDING
                entry.error = None
                pending += 1

            store.upsert_entry(entry)
            entries_out.append(asdict(entry) | {"on_chain_wei": on_chain_wei, "delta_wei": delta})
        except Exception as e:
            entry.status = SyncStatus.FAILED
            entry.error = str(e)
            store.upsert_entry(entry)
            failed += 1
            entries_out.append(asdict(entry) | {"error": str(e)})

    for item in entries_out:
        if "status" in item and hasattr(item["status"], "value"):
            item["status"] = item["status"].value

    return {
        "synced": synced,
        "pending": pending,
        "drifted": drifted,
        "failed": failed,
        "entries": entries_out,
    }
