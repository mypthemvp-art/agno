"""Deploy StartupStockToken contract via Foundry.

Requires Foundry (forge) installed: https://book.getfoundry.sh/

Prerequisites:
    export EVM_PRIVATE_KEY=0x<your-private-key>
    export EVM_RPC_URL=https://0xrpc.io/sep

Run:
    .venvs/demo/bin/python cookbook/91_tools/startup_stock/04_deploy_contract.py
"""

import json
import os

from agno.tools.startup_stock import StartupStockTools


def main() -> None:
    if not os.getenv("EVM_PRIVATE_KEY") or not os.getenv("EVM_RPC_URL"):
        print("Set EVM_PRIVATE_KEY and EVM_RPC_URL environment variables.")
        return

    tools = StartupStockTools(
        enable_deploy=True, enable_read=False, enable_write=False, enable_sync=False
    )

    print("=== Deploy StartupStockToken ===")
    result = json.loads(tools.deploy_token("Acme Startup", "ACME", 1_000_000.0))
    print(json.dumps(result, indent=2))

    if "contract_address" in result:
        print("\nSet this in your environment:")
        print(f"export STARTUP_STOCK_CONTRACT_ADDRESS={result['contract_address']}")


if __name__ == "__main__":
    main()
