"""Equity intelligence agent - cap table, vesting, dilution, and market comps.

Combines StartupStockAdvancedTools with FinanceTools for founders who need
equity analysis, funding scenario modeling, and public market comparisons.

Prerequisites:
    export EVM_PRIVATE_KEY=0x<your-private-key>
    export EVM_RPC_URL=https://0xrpc.io/sep
    export STARTUP_STOCK_CONTRACT_ADDRESS=0x<deployed-contract>
    export OPENAI_API_KEY=sk-...

Run:
    .venvs/demo/bin/python cookbook/91_tools/startup_stock/11_equity_intelligence_agent.py
"""

import os

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from agno.tools.finance import FinanceTools
from agno.tools.startup_stock import StartupStockAdvancedTools
from agno.tools.startup_stock.schemas import EquityIntelligenceReport


def main() -> None:
    if not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS"):
        print(
            "Set STARTUP_STOCK_CONTRACT_ADDRESS to a deployed StartupStockToken contract."
        )
        return

    tools = StartupStockAdvancedTools(
        enable_webhooks=False,
        enable_deploy_extended=False,
    )

    agent = Agent(
        name="Equity Intelligence Agent",
        model=OpenAIResponses(id="gpt-5.5"),
        tools=[tools, FinanceTools()],
        output_schema=EquityIntelligenceReport,
        instructions=[
            "You are an equity intelligence advisor for startup founders.",
            "Use startup stock tools for cap table, vesting, dilution, and compliance reports.",
            "Use finance tools to compare against public companies when asked.",
            "Generate equity reports and model dilution for funding scenarios.",
            "Check audit logs for recent cap table changes.",
            "Always preview sync with dry_run=True before recommending live sync.",
            "Never expose or request private keys.",
        ],
        markdown=True,
    )

    agent.print_response(
        "Generate a full equity intelligence report. "
        "Include cap table health, any vesting schedules, "
        "and model a Series A dilution with 25,000 new shares and 5,000 option pool increase. "
        "Compare our structure to a similar public SaaS company if possible.",
        stream=True,
    )


if __name__ == "__main__":
    main()
