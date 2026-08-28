"""Deploy StartupStockToken contracts via Foundry."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from agno.tools.startup_stock.base import shares_to_wei

CONTRACT_SOURCE = Path(__file__).parent / "contracts" / "StartupStockToken.sol"
VESTING_VAULT_SOURCE = Path(__file__).parent / "contracts" / "VestingVault.sol"
MULTISIG_SOURCE = Path(__file__).parent / "contracts" / "StartupStockMultiSig.sol"
DEPLOYED_ADDRESS_RE = re.compile(r"Deployed to:\s*(0x[a-fA-F0-9]{40})")


def _run_forge_create(
    source: Path,
    contract_name: str,
    rpc_url: str,
    private_key: str,
    constructor_args: Optional[list] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    """Run forge create and return deployment result or error dict."""
    forge = shutil.which("forge")
    if not forge:
        return {
            "error": "forge not found. Install Foundry: https://book.getfoundry.sh/getting-started/installation",
        }

    if not source.exists():
        return {"error": f"Contract source not found: {source}"}

    cmd = [
        forge,
        "create",
        str(source),
        f":{contract_name}",
        "--rpc-url",
        rpc_url,
        "--private-key",
        private_key,
        "--json",
    ]
    if constructor_args:
        cmd.extend(["--constructor-args", *[str(arg) for arg in constructor_args]])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": f"Deployment timed out after {timeout} seconds"}

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        return {"error": stderr or "Deployment failed"}

    try:
        payload = json.loads(result.stdout)
        address = payload.get("deployedTo") or payload.get("contractAddress")
    except json.JSONDecodeError:
        match = DEPLOYED_ADDRESS_RE.search(result.stdout)
        address = match.group(1) if match else None

    if not address:
        return {
            "error": "Deployment succeeded but contract address was not found in output",
            "stdout": result.stdout[:500],
        }

    return {"contract_address": address}


def deploy_startup_stock_token(
    name: str,
    symbol: str,
    max_supply_shares: float,
    rpc_url: str,
    private_key: str,
    contract_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Deploy StartupStockToken using Foundry's forge CLI.

    Requires Foundry (forge) to be installed: https://book.getfoundry.sh/
    """
    source = Path(contract_path) if contract_path else CONTRACT_SOURCE
    max_supply_wei = shares_to_wei(max_supply_shares)
    result = _run_forge_create(
        source=source,
        contract_name="StartupStockToken",
        rpc_url=rpc_url,
        private_key=private_key,
        constructor_args=[name, symbol, str(max_supply_wei)],
    )
    if "error" in result:
        return {**result, "name": name, "symbol": symbol}

    return {
        "contract_address": result["contract_address"],
        "name": name,
        "symbol": symbol,
        "max_supply_shares": max_supply_shares,
        "max_supply_wei": max_supply_wei,
        "rpc_url": rpc_url,
    }


def deploy_vesting_vault(
    token_address: str,
    rpc_url: str,
    private_key: str,
    contract_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Deploy VestingVault for a StartupStockToken address."""
    source = Path(contract_path) if contract_path else VESTING_VAULT_SOURCE
    result = _run_forge_create(
        source=source,
        contract_name="VestingVault",
        rpc_url=rpc_url,
        private_key=private_key,
        constructor_args=[token_address],
    )
    if "error" in result:
        return {**result, "token_address": token_address}

    return {
        "contract_address": result["contract_address"],
        "token_address": token_address,
        "rpc_url": rpc_url,
    }


def deploy_multisig(
    owners: list[str],
    required: int,
    rpc_url: str,
    private_key: str,
    contract_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Deploy StartupStockMultiSig with M-of-N owner configuration."""
    if not owners:
        return {"error": "At least one owner address is required"}
    if required <= 0 or required > len(owners):
        return {"error": "required must be between 1 and the number of owners"}

    source = Path(contract_path) if contract_path else MULTISIG_SOURCE
    result = _run_forge_create(
        source=source,
        contract_name="StartupStockMultiSig",
        rpc_url=rpc_url,
        private_key=private_key,
        constructor_args=[f"[{','.join(owners)}]", str(required)],
    )
    if "error" in result:
        return {**result, "owners": owners, "required": required}

    return {
        "contract_address": result["contract_address"],
        "owners": owners,
        "required": required,
        "rpc_url": rpc_url,
    }
