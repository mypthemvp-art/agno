"""Option pool, 409A valuation, and SAFE conversion example."""

import json
import os

from agno.tools.startup_stock import StartupStockAdvancedTools


def main() -> None:
    # Offline equity-instrument demo (still needs RPC/key for toolkit init).
    if not os.getenv("EVM_PRIVATE_KEY") or not os.getenv("EVM_RPC_URL"):
        print("Set EVM_PRIVATE_KEY and EVM_RPC_URL to run this example")
        return

    tools = StartupStockAdvancedTools(
        enable_webhooks=False,
        enable_deploy_extended=False,
        enable_vesting=False,
        enable_multisig=False,
    )

    print("=== Option Pool ===")
    print(tools.set_option_pool(100_000))
    grant = json.loads(
        tools.grant_options(
            recipient_name="Eve Engineer",
            shares=5_000,
            strike_price=0.50,
            recipient_wallet="0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
        )
    )
    print(json.dumps(grant, indent=2))
    print(tools.get_option_pool())

    print("=== 409A Valuation ===")
    print(
        tools.record_409a_valuation(
            fair_market_value=0.50,
            firm="Independent Valuations LLC",
            notes="Series Seed refresh",
        )
    )
    print(tools.check_409a_status())
    print(tools.suggest_option_strike())
    print(tools.compute_option_value(strike_price=0.50, shares=5_000))

    print("=== SAFE Instrument ===")
    instrument = json.loads(
        tools.add_safe_instrument(
            investor_name="Seed Fund",
            investment_amount=250_000,
            valuation_cap=5_000_000,
            discount_rate=0.20,
        )
    )
    print(json.dumps(instrument, indent=2))
    print(
        tools.preview_safe_conversion(
            instrument_id=instrument["instrument_id"],
            priced_round_price_per_share=2.0,
            pre_money_shares=2_500_000,
        )
    )
    print(tools.get_instruments_summary())


if __name__ == "__main__":
    main()
