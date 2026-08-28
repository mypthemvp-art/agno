"""Equity operations team - cap table, compliance, and investor relations.

Uses the Agno Team pattern to coordinate specialized agents for
startup equity management.

Prerequisites:
    export EVM_PRIVATE_KEY=0x<your-private-key>
    export EVM_RPC_URL=https://0xrpc.io/sep
    export STARTUP_STOCK_CONTRACT_ADDRESS=0x<deployed-contract>
    export OPENAI_API_KEY=sk-...

Run:
    .venvs/demo/bin/python cookbook/91_tools/startup_stock/13_equity_team.py
"""

import os

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from agno.team import Team
from agno.tools.finance import FinanceTools
from agno.tools.startup_stock import StartupStockAdvancedTools, StartupStockReader


def main() -> None:
    if not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS"):
        print("Set STARTUP_STOCK_CONTRACT_ADDRESS")
        return

    advanced_tools = StartupStockAdvancedTools(
        enable_webhooks=False,
        enable_deploy_extended=False,
    )

    cap_table_manager = Agent(
        name="Cap Table Manager",
        model=OpenAIResponses(id="gpt-5.5"),
        role="Manages cap table imports, sync, and vesting schedules.",
        tools=[advanced_tools],
        instructions=[
            "Manage the tokenized cap table: import, reconcile, sync with dry_run first.",
            "Create and track vesting schedules for investors.",
            "Never expose private keys.",
        ],
    )

    compliance_officer = Agent(
        name="Compliance Officer",
        model=OpenAIResponses(id="gpt-5.5"),
        role="Handles audit trails, compliance exports, and cap table snapshots.",
        tools=[advanced_tools],
        instructions=[
            "Generate equity reports and export compliance files.",
            "Create cap table snapshots before and after material changes.",
            "Review audit logs for traceability.",
        ],
    )

    investor_relations = Agent(
        name="Investor Relations",
        model=OpenAIResponses(id="gpt-5.5"),
        role="Answers investor questions and provides market context.",
        tools=[StartupStockReader(), FinanceTools()],
        instructions=[
            "Help investors check holdings using read-only tools.",
            "Compare startup equity structure to public companies when asked.",
            "Never request private keys.",
        ],
    )

    team = Team(
        name="Startup Equity Team",
        model=OpenAIResponses(id="gpt-5.5"),
        members=[cap_table_manager, compliance_officer, investor_relations],
        instructions=[
            "Coordinate startup equity operations across cap table, compliance, and IR.",
            "Cap Table Manager handles sync and vesting.",
            "Compliance Officer handles reports, snapshots, and audit.",
            "Investor Relations handles read-only investor queries and market comps.",
        ],
        markdown=True,
        show_members_responses=True,
    )

    team.print_response(
        "Review our cap table health, create a pre-funding snapshot labeled 'pre-series-a', "
        "and summarize what sync actions are needed.",
        stream=True,
    )


if __name__ == "__main__":
    main()
