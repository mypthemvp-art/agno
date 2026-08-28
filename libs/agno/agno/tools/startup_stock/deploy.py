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
DEPLOYED_ADDRESS_RE = re.compile(r"Deployed to:\s*(0x[a-fA-F0-9]{40})")


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
    forge = shutil.which("forge")
    if not forge:
        return {
            "error": "forge not found. Install Foundry: https://book.getfoundry.sh/getting-started/installation",
            "name": name,
            "symbol": symbol,
        }

    source = Path(contract_path) if contract_path else CONTRACT_SOURCE
    if not source.exists():
        return {"error": f"Contract source not found: {source}", "name": name, "symbol": symbol}

    max_supply_wei = shares_to_wei(max_supply_shares)
    cmd = [
        forge,
        "create",
        str(source),
        ":StartupStockToken",
        "--rpc-url",
        rpc_url,
        "--private-key",
        private_key,
        "--constructor-args",
        name,
        symbol,
        str(max_supply_wei),
        "--json",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
    except subprocess.TimeoutExpired:
        return {"error": "Deployment timed out after 300 seconds", "name": name, "symbol": symbol}

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        return {"error": stderr or "Deployment failed", "name": name, "symbol": symbol}

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
            "name": name,
            "symbol": symbol,
        }

    return {
        "contract_address": address,
        "name": name,
        "symbol": symbol,
        "max_supply_shares": max_supply_shares,
        "max_supply_wei": max_supply_wei,
        "rpc_url": rpc_url,
    }
