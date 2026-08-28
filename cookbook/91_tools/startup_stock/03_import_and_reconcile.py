"""Import cap table from CSV and reconcile with on-chain state.

Prerequisites:
    export EVM_PRIVATE_KEY=0x<your-private-key>
    export EVM_RPC_URL=https://0xrpc.io/sep
    export STARTUP_STOCK_CONTRACT_ADDRESS=0x<deployed-contract>

Run:
    .venvs/demo/bin/python cookbook/91_tools/startup_stock/03_import_and_reconcile.py
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
        return

    db_path = str(Path(tempfile.gettempdir()) / "startup_stock_import_demo.db")
    csv_path = str(Path(__file__).parent / "sample_cap_table.csv")

    tools = StartupStockTools(cap_table_db=db_path)

    print("=== Import Cap Table ===")
    result = json.loads(tools.import_cap_table(csv_path))
    print(json.dumps(result, indent=2))

    print("\n=== Cap Table ===")
    cap_table = json.loads(tools.list_cap_table())
    for entry in cap_table.get("entries", []):
        print(
            f"  {entry['investor_name']}: {entry['shares']} shares ({entry['status']})"
        )

    print("\n=== Reconcile On-Chain ===")
    reconcile = json.loads(tools.reconcile_cap_table())
    print(f"  Synced:  {reconcile.get('synced', 0)}")
    print(f"  Pending: {reconcile.get('pending', 0)}")
    print(f"  Drifted: {reconcile.get('drifted', 0)}")
    print(f"  Failed:  {reconcile.get('failed', 0)}")

    print("\n=== Dry Run Sync ===")
    dry_result = json.loads(tools.sync_cap_table(dry_run=True))
    print(f"  Skipped (pending mint): {dry_result.get('skipped', 0)}")


if __name__ == "__main__":
    main()
