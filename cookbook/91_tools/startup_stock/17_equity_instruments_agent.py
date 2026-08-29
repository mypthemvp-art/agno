"""Equity instruments agent: option pool, 409A, and SAFE advisory."""

import os

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from agno.tools.startup_stock import StartupStockAdvancedTools
from agno.tools.startup_stock.schemas import EquityIntelligenceReport


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY to run this example")
        return
    if not os.getenv("EVM_PRIVATE_KEY") or not os.getenv("EVM_RPC_URL"):
        print("Set EVM_PRIVATE_KEY and EVM_RPC_URL to run this example")
        return

    tools = StartupStockAdvancedTools(
        enable_webhooks=False,
        enable_deploy_extended=False,
    )

    agent = Agent(
        model=OpenAIResponses(id="gpt-5.5"),
        tools=[tools],
        output_schema=EquityIntelligenceReport,
        instructions=(
            "You advise startup founders on option pools, 409A valuations, "
            "and SAFE/SAFT conversion. Use tools for facts; keep recommendations concrete."
        ),
        markdown=True,
    )

    agent.print_response(
        "Set a 100000 share option pool, record a $0.40 409A from Acme Valuations, "
        "grant 2500 options at the suggested strike to engineer Dana, add a $100k SAFE "
        "with a $4M cap and 20% discount, then summarize pool utilization and SAFE exposure.",
        stream=True,
    )


if __name__ == "__main__":
    main()
