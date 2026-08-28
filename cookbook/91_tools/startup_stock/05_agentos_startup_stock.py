"""Startup Stock AgentOS - serve equity management as an API.

Investors can query balances via StartupStockReader (no private key).
Founders use StartupStockTools for full cap table management.

Prerequisites:
    export EVM_RPC_URL=https://0xrpc.io/sep
    export STARTUP_STOCK_CONTRACT_ADDRESS=0x<deployed-contract>
    export EVM_PRIVATE_KEY=0x<founder-private-key>   # for write operations
    export OPENAI_API_KEY=sk-...

Run:
    .venvs/demo/bin/python cookbook/91_tools/startup_stock/05_agentos_startup_stock.py

Open:
    http://localhost:7777/config
"""

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIResponses
from agno.os import AgentOS
from agno.tools.finance import FinanceTools
from agno.tools.startup_stock import StartupStockReader, StartupStockTools
from pydantic import BaseModel


class EquityReport(BaseModel):
    summary: str
    token_symbol: str
    recommendations: list[str]


db = SqliteDb(id="startup-stock-os-db", db_file="tmp/startup_stock_os.db")

investor_agent = Agent(
    id="startup-stock-investor",
    name="Startup Stock Investor",
    model=OpenAIResponses(id="gpt-5.5"),
    tools=[StartupStockReader()],
    instructions=[
        "You help investors check their tokenized startup equity holdings.",
        "Use read-only startup stock tools. Never request private keys.",
        "Provide clear share balances and token metadata.",
    ],
    markdown=True,
)

founder_agent = Agent(
    id="startup-stock-founder",
    name="Startup Stock Founder",
    model=OpenAIResponses(id="gpt-5.5"),
    db=db,
    tools=[StartupStockTools(), FinanceTools()],
    output_schema=EquityReport,
    instructions=[
        "You help startup founders manage tokenized equity cap tables.",
        "Import CSV cap tables, reconcile on-chain state, and preview sync with dry_run=True.",
        "Use finance tools for public market comparisons when asked.",
        "Never expose or request private keys.",
    ],
    add_history_to_context=True,
    num_history_runs=3,
    markdown=True,
)

agent_os = AgentOS(
    id="startup-stock-os",
    description="Tokenized startup equity management for founders and investors.",
    agents=[investor_agent, founder_agent],
)
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="05_agentos_startup_stock:app", reload=True)
