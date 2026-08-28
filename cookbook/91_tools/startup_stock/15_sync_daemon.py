"""Continuous cap table sync daemon example."""

import json
import os
import sys

from agno.tools.startup_stock import StartupStockAdvancedTools
from agno.tools.startup_stock.sync_daemon import CapTableSyncDaemon


def main() -> None:
    if not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS"):
        print("Set STARTUP_STOCK_CONTRACT_ADDRESS")
        return

    tools = StartupStockAdvancedTools(
        enable_webhooks=False,
        enable_deploy_extended=False,
    )

    iterations = 3
    if len(sys.argv) > 1:
        try:
            iterations = int(sys.argv[1])
        except ValueError:
            print("Usage: python 15_sync_daemon.py [max_iterations]")
            return

    def sync_fn(dry_run: bool) -> dict:
        return json.loads(tools.sync_cap_table(dry_run=dry_run))

    daemon = CapTableSyncDaemon(
        sync_fn=sync_fn,
        poll_interval_seconds=10.0,
        dry_run=True,
        on_sync=lambda r: print(json.dumps(r)),
    )

    print(f"=== Sync Daemon ({iterations} iterations, dry-run) ===")
    daemon.run(max_iterations=iterations)


if __name__ == "__main__":
    main()
