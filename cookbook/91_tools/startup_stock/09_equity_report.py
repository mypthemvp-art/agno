"""Equity report, dilution modeling, and compliance export example."""

import json

from agno.tools.startup_stock import StartupStockAdvancedTools


def main() -> None:
    tools = StartupStockAdvancedTools(
        enable_multisig=False,
        enable_webhooks=False,
        enable_deploy_extended=False,
    )

    tools.add_investor("Alice", "0x742d35Cc6634C0532925a3b8D2A7E1234567890A", 60000.0)
    tools.add_investor("Bob", "0x3Dfc53E3C77bb4e30Ce333Be1a66Ce62558bE395", 40000.0)

    print("=== Equity Report ===")
    report = json.loads(tools.generate_equity_report())
    print(json.dumps(report, indent=2))

    print("\n=== Series A Dilution (20,000 new shares) ===")
    dilution = json.loads(
        tools.calculate_dilution(
            scenario_name="Series A",
            new_shares=20000.0,
            option_pool_increase=5000.0,
        )
    )
    print(json.dumps(dilution, indent=2))

    print("\n=== Export Compliance Report ===")
    export_result = json.loads(
        tools.export_compliance_report("tmp/equity_compliance_report.json", fmt="json")
    )
    print(json.dumps(export_result, indent=2))


if __name__ == "__main__":
    main()
