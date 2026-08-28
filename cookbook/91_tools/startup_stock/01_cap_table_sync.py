"""Cap table sync example for startup stock tokenization.

Demonstrates adding investors to a local cap table and syncing
share allocations to the blockchain with dry-run preview.

Prerequisites:
    export EVM_PRIVATE_KEY=0x<your-private-key>
    export EVM_RPC_URL=https://0xrpc.io/sep
    export STARTUP_STOCK_CONTRACT_ADDRESS=0x<deployed-contract>

Run:
    .venvs/demo/bin/python cookbook/91_tools/startup_stock/01_cap_table_sync.py
"""

import json
import os
import tempfile
from pathlib import Path

from agno.tools.startup_stock import StartupStockTools


def main() -> None:
    if not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS"):
        print(
            "Set STARTUP_STOCK_CONTRACT_ADDRESS to a deployed StartupStockToken contract."
        )
        print("See README.md for deployment instructions.")
        return

    db_path = str(Path(tempfile.gettempdir()) / "startup_stock_demo.db")

    tools = StartupStockTools(cap_table_db=db_path)

    print("=== Token Info ===")
    print(json.dumps(json.loads(tools.get_token_info()), indent=2))

    print("\n=== Adding Investors ===")
    investors = [
        ("Alice Chen", "0x742d35Cc6634C0532925a3b8D2A7E1234567890A", 10000.0),
        ("Bob Martinez", "0x3Dfc53E3C77bb4e30Ce333Be1a66Ce62558bE395", 5000.0),
        ("Carol Williams", "0x1111111111111111111111111111111111111111", 2500.0),
    ]
    for name, wallet, shares in investors:
        result = json.loads(tools.add_investor(name, wallet, shares))
        print(f"  Added {name}: {shares} shares -> {result.get('status', 'ok')}")

    print("\n=== Cap Table ===")
    cap_table = json.loads(tools.list_cap_table())
    for entry in cap_table.get("entries", []):
        print(
            f"  {entry['investor_name']}: {entry['shares']} shares ({entry['status']})"
        )

    print("\n=== Dry Run Sync ===")
    dry_result = json.loads(tools.sync_cap_table(dry_run=True))
    print(f"  Would sync: {dry_result.get('skipped', 0)} entries pending mint")
    for entry in dry_result.get("entries", []):
        if entry.get("mint_delta_wei"):
            print(
                f"  {entry['investor_name']}: would mint {entry['mint_delta_wei']} wei"
            )

    print("\n=== Live Sync ===")
    print("Uncomment the line below to execute on-chain minting:")
    print("# live_result = json.loads(tools.sync_cap_table(dry_run=False))")
    print("# print(json.dumps(live_result, indent=2))")


if __name__ == "__main__":
    main()
