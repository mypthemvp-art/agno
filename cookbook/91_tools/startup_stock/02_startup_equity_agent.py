"""Startup equity agent - AI-powered cap table management.

Uses StartupStockTools and FinanceTools to manage tokenized startup equity
with natural language. The agent reads on-chain state, manages the cap table,
and can preview blockchain sync operations.

Prerequisites:
    export EVM_PRIVATE_KEY=0x<your-private-key>
    export EVM_RPC_URL=https://0xrpc.io/sep
    export STARTUP_STOCK_CONTRACT_ADDRESS=0x<deployed-contract>
    export OPENAI_API_KEY=sk-...

Run:
    .venvs/demo/bin/python cookbook/91_tools/startup_stock/02_startup_equity_agent.py
"""

import os

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from agno.tools.finance import FinanceTools
from agno.tools.startup_stock import StartupStockTools
from pydantic import BaseModel


class EquitySummary(BaseModel):
    company_token: str
    total_investors: int
    total_shares_allocated: float
    sync_status: str
    recommendations: list[str]


def main() -> None:
    if not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS"):
        print(
            "Set STARTUP_STOCK_CONTRACT_ADDRESS to a deployed StartupStockToken contract."
        )
        return

    agent = Agent(
        name="Startup Equity Agent",
        model=OpenAIResponses(id="gpt-5.5"),
        tools=[
            StartupStockTools(),
            FinanceTools(),
        ],
        output_schema=EquitySummary,
        instructions=[
            "You manage tokenized startup equity on EVM blockchains.",
            "Use startup stock tools for cap table and on-chain operations.",
            "Use finance tools to look up public company data when asked for market comparisons.",
            "Always run sync_cap_table with dry_run=True before recommending live sync.",
            "Never expose or request private keys.",
            "Provide clear, actionable recommendations for founders.",
        ],
        markdown=True,
    )

    agent.print_response(
        "Show me the current token info and cap table status. "
        "Summarize what sync actions would be needed.",
        stream=True,
    )


if __name__ == "__main__":
    main()
