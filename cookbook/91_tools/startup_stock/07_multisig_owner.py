"""Multi-sig owner example for startup stock contracts."""

import json
import os

from agno.tools.startup_stock import StartupStockAdvancedTools
from agno.tools.startup_stock.base import shares_to_wei


def main() -> None:
    if not os.getenv("STARTUP_STOCK_MULTISIG_ADDRESS"):
        print(
            "Set STARTUP_STOCK_MULTISIG_ADDRESS to a deployed StartupStockMultiSig contract."
        )
        return

    tools = StartupStockAdvancedTools(enable_vesting=False, enable_webhooks=False)

    print("=== Multi-Sig Info ===")
    info = json.loads(tools.get_multisig_info())
    print(json.dumps(info, indent=2))

    contract = tools._require_contract().contract
    multisig = tools._require_multisig()
    mint_data = multisig.encode_token_mint(
        contract,
        "0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
        shares_to_wei(1000.0),
    )

    print("\n=== Submit Mint Transaction ===")
    print("Uncomment to submit on-chain:")
    print("# result = tools.submit_multisig_transaction(")
    print(f"#     target='{tools.contract_address}',")
    print(f"#     data_hex='0x{mint_data.hex()}',")
    print("# )")


if __name__ == "__main__":
    main()
