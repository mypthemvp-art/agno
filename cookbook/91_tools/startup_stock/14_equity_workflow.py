"""Equity workflow - programmatic import-to-export pipeline.

Uses the Agno Workflow pattern with function steps for deterministic
cap table operations without LLM calls per step.

Prerequisites:
    export EVM_PRIVATE_KEY=0x<your-private-key>
    export EVM_RPC_URL=https://0xrpc.io/sep
    export STARTUP_STOCK_CONTRACT_ADDRESS=0x<deployed-contract>

Run:
    .venvs/demo/bin/python cookbook/91_tools/startup_stock/14_equity_workflow.py
"""

import json
import os
from pathlib import Path

from agno.db.sqlite import SqliteDb
from agno.tools.startup_stock import StartupStockAdvancedTools
from agno.workflow.types import StepInput, StepOutput
from agno.workflow.workflow import Workflow


def _get_tools() -> StartupStockAdvancedTools:
    return StartupStockAdvancedTools(
        enable_webhooks=False,
        enable_deploy_extended=False,
    )


def step_health_check(step_input: StepInput) -> StepOutput:
    tools = _get_tools()
    result = json.loads(tools.run_health_check())
    healthy = result.get("healthy", False)
    return StepOutput(content=json.dumps(result, indent=2), success=healthy)


def step_import_cap_table(step_input: StepInput) -> StepOutput:
    tools = _get_tools()
    csv_path = str(Path(__file__).parent / "sample_cap_table.csv")
    result = json.loads(tools.import_cap_table(csv_path))
    ok = "error" not in result
    return StepOutput(content=json.dumps(result, indent=2), success=ok)


def step_create_snapshot(step_input: StepInput) -> StepOutput:
    tools = _get_tools()
    result = json.loads(tools.create_cap_table_snapshot("workflow-start"))
    ok = "error" not in result
    return StepOutput(content=json.dumps(result, indent=2), success=ok)


def step_reconcile_and_sync(step_input: StepInput) -> StepOutput:
    tools = _get_tools()
    reconcile = json.loads(tools.reconcile_cap_table())
    sync = json.loads(tools.sync_cap_table(dry_run=True))
    combined = {"reconcile": reconcile, "sync_dry_run": sync}
    ok = "error" not in reconcile and "error" not in sync
    return StepOutput(content=json.dumps(combined, indent=2), success=ok)


def step_report_and_export(step_input: StepInput) -> StepOutput:
    tools = _get_tools()
    report = json.loads(tools.generate_equity_report())
    export = json.loads(
        tools.export_compliance_report("tmp/workflow_compliance.json", fmt="json")
    )
    snapshot = json.loads(tools.create_cap_table_snapshot("workflow-end"))
    combined = {
        "report_summary": report.get("summary"),
        "export": export,
        "snapshot": snapshot,
    }
    ok = "error" not in report and "error" not in export
    return StepOutput(content=json.dumps(combined, indent=2), success=ok)


equity_workflow = Workflow(
    name="Startup Equity Workflow",
    description="Import, snapshot, reconcile, sync preview, report, and export.",
    db=SqliteDb(db_file="tmp/startup_stock_workflow.db"),
    steps=[
        step_health_check,
        step_import_cap_table,
        step_create_snapshot,
        step_reconcile_and_sync,
        step_report_and_export,
    ],
)


def main() -> None:
    if not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS"):
        print("Set STARTUP_STOCK_CONTRACT_ADDRESS")
        return

    print("=== Equity Workflow ===")
    equity_workflow.print_response(
        input="Run the startup equity pipeline",
        stream=False,
    )


if __name__ == "__main__":
    main()
