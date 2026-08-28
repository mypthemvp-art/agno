"""Continuous transfer webhook daemon example."""

import json
import os
import sys

from agno.tools.startup_stock import StartupStockAdvancedTools
from agno.tools.startup_stock.webhook_daemon import TransferWebhookDaemon


def main() -> None:
    if not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS"):
        print("Set STARTUP_STOCK_CONTRACT_ADDRESS")
        return
    if not os.getenv("STARTUP_STOCK_WEBHOOK_URL"):
        print("Set STARTUP_STOCK_WEBHOOK_URL")
        return

    tools = StartupStockAdvancedTools(
        enable_vesting=False,
        enable_multisig=False,
        enable_reports=False,
        enable_deploy_extended=False,
    )

    iterations = 3
    if len(sys.argv) > 1:
        try:
            iterations = int(sys.argv[1])
        except ValueError:
            print("Usage: python 10_webhook_daemon.py [max_iterations]")
            return

    watcher = tools._build_webhook_watcher()
    daemon = TransferWebhookDaemon(
        watcher=watcher,
        poll_interval_seconds=5.0,
        lookback_blocks=50,
        on_poll=lambda result: print(json.dumps(result)),
    )

    print(f"=== Webhook Daemon ({iterations} iterations) ===")
    daemon.run(max_iterations=iterations)


if __name__ == "__main__":
    main()
