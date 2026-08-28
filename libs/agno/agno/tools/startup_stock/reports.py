"""Equity reports, dilution modeling, and compliance exports."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from agno.tools.startup_stock.sync import CapTableStore
from agno.tools.startup_stock.vesting import VestingStore, compute_releasable_shares, compute_vested_shares


class BalanceReader(Protocol):
    def get_balance(self, wallet_address: str) -> int: ...


@dataclass
class DilutionScenario:
    name: str
    new_shares: float
    option_pool_increase: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_dilution(
    shareholders: List[Dict[str, Any]],
    scenarios: List[DilutionScenario],
) -> Dict[str, Any]:
    """Calculate ownership dilution across funding scenarios."""
    total_shares = sum(s.get("shares", 0) for s in shareholders)
    if total_shares <= 0:
        return {"error": "No shares outstanding", "shareholders": shareholders}

    base_ownership = [
        {
            "investor_name": s.get("investor_name", s.get("wallet_address", "?")),
            "wallet_address": s.get("wallet_address", ""),
            "shares": s.get("shares", 0),
            "ownership_pct": round(100 * s.get("shares", 0) / total_shares, 4),
        }
        for s in shareholders
    ]

    scenario_results = []
    for scenario in scenarios:
        new_total = total_shares + scenario.new_shares + scenario.option_pool_increase
        diluted = [
            {
                "investor_name": s["investor_name"],
                "wallet_address": s["wallet_address"],
                "shares": s["shares"],
                "ownership_pct": round(100 * s["shares"] / new_total, 4),
                "dilution_pct": round(s["ownership_pct"] - 100 * s["shares"] / new_total, 4),
            }
            for s in base_ownership
        ]
        scenario_results.append(
            {
                "scenario": scenario.to_dict(),
                "post_money_shares": new_total,
                "shareholders": diluted,
            }
        )

    return {
        "total_shares": total_shares,
        "shareholder_count": len(shareholders),
        "base_ownership": base_ownership,
        "scenarios": scenario_results,
    }


def generate_equity_report(
    cap_table_store: CapTableStore,
    vesting_store: Optional[VestingStore] = None,
    on_chain_reader: Optional[BalanceReader] = None,
    shares_to_wei=None,
    wei_to_shares=None,
) -> Dict[str, Any]:
    """Generate a comprehensive equity report with on-chain verification."""
    entries = cap_table_store.list_entries()
    total_allocated = sum(e.shares for e in entries)

    investors: List[Dict[str, Any]] = []
    synced_count = pending_count = drift_count = 0

    for entry in entries:
        status = entry.status.value if hasattr(entry.status, "value") else str(entry.status)
        if status == "synced":
            synced_count += 1
        elif status == "drift":
            drift_count += 1
        else:
            pending_count += 1

        investor: Dict[str, Any] = {
            "investor_name": entry.investor_name,
            "wallet_address": entry.wallet_address,
            "shares": entry.shares,
            "status": status,
            "checksum": entry.checksum,
            "ownership_pct": 0.0,
        }

        if on_chain_reader and shares_to_wei and wei_to_shares:
            try:
                on_chain_wei = on_chain_reader.get_balance(entry.wallet_address)
                investor["on_chain_shares"] = wei_to_shares(on_chain_wei)
                investor["on_chain_verified"] = on_chain_wei == shares_to_wei(entry.shares)
            except Exception as e:
                investor["on_chain_error"] = str(e)

        if vesting_store:
            schedule = vesting_store.get(entry.wallet_address)
            if schedule:
                investor["vesting"] = {
                    "total_shares": schedule.total_shares,
                    "vested_shares": compute_vested_shares(schedule),
                    "releasable_shares": compute_releasable_shares(schedule),
                    "cliff_seconds": schedule.cliff_seconds,
                    "vesting_seconds": schedule.vesting_seconds,
                    "revoked": schedule.revoked,
                }

        investors.append(investor)

    if total_allocated > 0:
        for inv in investors:
            inv["ownership_pct"] = round(100 * inv["shares"] / total_allocated, 4)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "investor_count": len(entries),
            "total_allocated_shares": total_allocated,
            "synced": synced_count,
            "pending": pending_count,
            "drifted": drift_count,
        },
        "investors": investors,
    }


def export_compliance_report(
    report: Dict[str, Any],
    file_path: str,
    fmt: str = "json",
) -> Dict[str, Any]:
    """Export equity report to JSON or CSV for compliance/audit."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "csv":
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "investor_name",
                    "wallet_address",
                    "shares",
                    "ownership_pct",
                    "status",
                    "on_chain_shares",
                    "on_chain_verified",
                    "checksum",
                ],
            )
            writer.writeheader()
            for inv in report.get("investors", []):
                writer.writerow(
                    {
                        "investor_name": inv.get("investor_name", ""),
                        "wallet_address": inv.get("wallet_address", ""),
                        "shares": inv.get("shares", 0),
                        "ownership_pct": inv.get("ownership_pct", 0),
                        "status": inv.get("status", ""),
                        "on_chain_shares": inv.get("on_chain_shares", ""),
                        "on_chain_verified": inv.get("on_chain_verified", ""),
                        "checksum": inv.get("checksum", ""),
                    }
                )
    else:
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    return {"file_path": str(path), "format": fmt, "investor_count": report.get("summary", {}).get("investor_count", 0)}
