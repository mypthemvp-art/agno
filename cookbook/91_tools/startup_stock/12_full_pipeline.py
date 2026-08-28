"""Full pipeline demo - import, sync, vest, report, export, audit.

Walks through the complete startup equity lifecycle without live on-chain
transactions (uses dry-run sync). Requires a deployed contract for read ops.

Prerequisites:
    export EVM_PRIVATE_KEY=0x<your-private-key>
    export EVM_RPC_URL=https://0xrpc.io/sep
    export STARTUP_STOCK_CONTRACT_ADDRESS=0x<deployed-contract>

Run:
    .venvs/demo/bin/python cookbook/91_tools/startup_stock/12_full_pipeline.py
"""

import json
import os
from pathlib import Path

from agno.tools.startup_stock import StartupStockAdvancedTools
from agno.tools.startup_stock.schemas import PipelineStatus


def _step(name: str, fn) -> PipelineStatus:
    try:
        detail = fn()
        status = (
            "ok" if not (isinstance(detail, dict) and detail.get("error")) else "error"
        )
        return PipelineStatus(step=name, status=status, detail=str(detail)[:200])
    except Exception as e:
        return PipelineStatus(step=name, status="error", detail=str(e))


def main() -> None:
    if not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS"):
        print("Set STARTUP_STOCK_CONTRACT_ADDRESS")
        return

    tools = StartupStockAdvancedTools(
        enable_webhooks=False,
        enable_deploy_extended=False,
    )

    sample_csv = str(Path(__file__).parent / "sample_cap_table.csv")
    results: list[PipelineStatus] = []

    print("=== Startup Stock Full Pipeline ===\n")

    results.append(
        _step(
            "import_cap_table",
            lambda: json.loads(tools.import_cap_table(sample_csv)),
        )
    )

    results.append(
        _step(
            "reconcile",
            lambda: json.loads(tools.reconcile_cap_table()),
        )
    )

    results.append(
        _step(
            "sync_dry_run",
            lambda: json.loads(tools.sync_cap_table(dry_run=True)),
        )
    )

    beneficiary = "0x742d35Cc6634C0532925a3b8D2A7E1234567890A"
    results.append(
        _step(
            "create_vesting",
            lambda: json.loads(
                tools.create_vesting_schedule(
                    beneficiary=beneficiary,
                    total_shares=5000.0,
                    cliff_days=0,
                    vesting_days=365,
                )
            ),
        )
    )

    results.append(
        _step(
            "equity_report",
            lambda: json.loads(tools.generate_equity_report()),
        )
    )

    results.append(
        _step(
            "dilution_model",
            lambda: json.loads(
                tools.calculate_dilution(
                    scenario_name="Series A",
                    new_shares=20000.0,
                    option_pool_increase=5000.0,
                )
            ),
        )
    )

    export_path = "tmp/pipeline_compliance_report.json"
    results.append(
        _step(
            "export_compliance",
            lambda: json.loads(tools.export_compliance_report(export_path, fmt="json")),
        )
    )

    results.append(
        _step(
            "audit_log",
            lambda: json.loads(tools.get_audit_log(limit=20)),
        )
    )

    for r in results:
        marker = "PASS" if r.status == "ok" else "FAIL"
        print(f"[{marker}] {r.step}: {r.detail or r.status}")

    passed = sum(1 for r in results if r.status == "ok")
    print(f"\nPipeline complete: {passed}/{len(results)} steps passed")


if __name__ == "__main__":
    main()
