"""Health checks for startup stock infrastructure."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from agno.tools.startup_stock.sync import CapTableStore, SyncStatus


class RpcClient(Protocol):
    def is_connected(self) -> bool: ...

    @property
    def eth(self) -> Any: ...


class ContractReader(Protocol):
    def get_token_info_dict(self, wallet_address: Optional[str] = None) -> Dict[str, Any]: ...


def check_rpc_health(web3_client: RpcClient) -> Dict[str, Any]:
    """Verify RPC connectivity and chain ID."""
    try:
        connected = web3_client.is_connected()
        chain_id = web3_client.eth.chain_id if connected else None
        block = web3_client.eth.block_number if connected else None
        return {
            "component": "rpc",
            "healthy": connected and chain_id is not None,
            "chain_id": chain_id,
            "latest_block": block,
        }
    except Exception as e:
        return {"component": "rpc", "healthy": False, "error": str(e)}


def check_contract_health(contract_client: ContractReader) -> Dict[str, Any]:
    """Verify contract is reachable and returns token metadata."""
    try:
        info = contract_client.get_token_info_dict()
        if "error" in info:
            return {"component": "contract", "healthy": False, "error": info["error"]}
        return {
            "component": "contract",
            "healthy": True,
            "name": info.get("name"),
            "symbol": info.get("symbol"),
            "contract_address": info.get("contract_address"),
        }
    except Exception as e:
        return {"component": "contract", "healthy": False, "error": str(e)}


def check_cap_table_health(store: CapTableStore) -> Dict[str, Any]:
    """Summarize cap table sync health."""
    entries = store.list_entries()
    pending = drift = synced = failed = 0
    for entry in entries:
        if entry.status == SyncStatus.PENDING:
            pending += 1
        elif entry.status == SyncStatus.DRIFT:
            drift += 1
        elif entry.status == SyncStatus.SYNCED:
            synced += 1
        elif entry.status == SyncStatus.FAILED:
            failed += 1

    if drift > 0:
        overall = "critical"
    elif pending > 0 or failed > 0:
        overall = "degraded"
    elif not entries:
        overall = "empty"
    else:
        overall = "healthy"

    return {
        "component": "cap_table",
        "healthy": overall in ("healthy", "empty"),
        "status": overall,
        "investor_count": len(entries),
        "synced": synced,
        "pending": pending,
        "drifted": drift,
        "failed": failed,
    }


def run_health_check(
    web3_client: Optional[RpcClient] = None,
    contract_client: Optional[ContractReader] = None,
    cap_table_store: Optional[CapTableStore] = None,
    vesting_vault_configured: bool = False,
    multisig_configured: bool = False,
    webhook_configured: bool = False,
) -> Dict[str, Any]:
    """Run all available health checks and return aggregate status."""
    checks: List[Dict[str, Any]] = []

    if web3_client:
        checks.append(check_rpc_health(web3_client))
    if contract_client:
        checks.append(check_contract_health(contract_client))
    if cap_table_store:
        checks.append(check_cap_table_health(cap_table_store))

    checks.append(
        {
            "component": "vesting_vault",
            "healthy": True,
            "configured": vesting_vault_configured,
        }
    )
    checks.append(
        {
            "component": "multisig",
            "healthy": True,
            "configured": multisig_configured,
        }
    )
    checks.append(
        {
            "component": "webhooks",
            "healthy": True,
            "configured": webhook_configured,
        }
    )

    core_checks = [c for c in checks if c.get("component") in ("rpc", "contract", "cap_table")]
    all_healthy = all(c.get("healthy", False) for c in core_checks) if core_checks else True

    return {
        "healthy": all_healthy,
        "checks": checks,
        "check_count": len(checks),
    }
