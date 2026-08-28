"""Vesting schedule example for startup equity."""

import json
import time

from agno.tools.startup_stock import StartupStockAdvancedTools


def main() -> None:
    tools = StartupStockAdvancedTools(enable_multisig=False, enable_webhooks=False)

    beneficiary = "0x742d35Cc6634C0532925a3b8D2A7E1234567890A"

    print("=== Create Vesting Schedule ===")
    result = json.loads(
        tools.create_vesting_schedule(
            beneficiary=beneficiary,
            total_shares=10000.0,
            cliff_days=365,
            vesting_days=1460,
            start_timestamp=int(time.time()),
        )
    )
    print(json.dumps(result, indent=2))

    print("\n=== Vesting Status ===")
    status = json.loads(tools.get_vesting_schedule(beneficiary))
    print(json.dumps(status, indent=2))

    print("\n=== All Schedules ===")
    schedules = json.loads(tools.list_vesting_schedules())
    print(json.dumps(schedules, indent=2))


if __name__ == "__main__":
    main()
