"""Option pool grants and transfer policy example."""

import json
import os

from agno.tools.startup_stock import StartupStockAdvancedTools


def main() -> None:
    if not os.getenv("EVM_PRIVATE_KEY") or not os.getenv("EVM_RPC_URL"):
        print("Set EVM_PRIVATE_KEY and EVM_RPC_URL to run this example")
        return

    tools = StartupStockAdvancedTools(
        enable_webhooks=False,
        enable_deploy_extended=False,
        enable_vesting=False,
        enable_multisig=False,
    )

    print("=== Set Option Pool (10,000 shares) ===")
    print(json.dumps(json.loads(tools.set_option_pool(10000)), indent=2))

    print("\n=== Grant Options ===")
    grant = json.loads(
        tools.grant_options(
            recipient_name="Lead Engineer",
            shares=2500,
            strike_price=0.50,
            recipient_wallet="0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
            cliff_days=365,
            vesting_days=1460,
        )
    )
    print(json.dumps(grant, indent=2))

    print("\n=== Option Pool Summary ===")
    print(json.dumps(json.loads(tools.get_option_pool()), indent=2))

    print("\n=== Configure Transfer Policy ===")
    print(
        json.dumps(
            json.loads(
                tools.update_transfer_policy(restricted=True, require_allowlist=True)
            ),
            indent=2,
        )
    )
    tools.add_transfer_allowlist(tools.account.address, label="company-wallet")
    tools.add_transfer_allowlist(
        "0x742d35Cc6634C0532925a3b8D2A7E1234567890A", label="employee"
    )

    print("\n=== Check Transfer Allowed ===")
    print(
        json.dumps(
            json.loads(
                tools.check_transfer_allowed(
                    tools.account.address,
                    "0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
                )
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
