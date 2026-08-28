"""Read-only startup stock toolkit for investors and auditors."""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from agno.tools.startup_stock.base import StartupStockContract, wei_to_shares
from agno.tools.toolkit import Toolkit


class StartupStockReader(Toolkit):
    """Read-only access to startup stock tokens. No private key required.

    Investors and auditors can query token metadata and wallet balances
    without write access to the blockchain.
    """

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        contract_address: Optional[str] = None,
        **kwargs,
    ):
        self.contract_client = StartupStockContract(
            rpc_url=rpc_url,
            contract_address=contract_address,
        )

        tools: List[Callable[..., str]] = [
            self.get_token_info,
            self.get_investor_balance,
        ]
        async_tools: List[tuple[Callable[..., Any], str]] = [
            (self.aget_token_info, "get_token_info"),
            (self.aget_investor_balance, "get_investor_balance"),
        ]

        super().__init__(
            name="startup_stock_reader",
            tools=tools,
            async_tools=async_tools,
            instructions=(
                "Read-only startup stock tools. Query token info and investor balances. "
                "Cannot mint, transfer, or modify the cap table."
            ),
            **kwargs,
        )

    def get_token_info(self) -> str:
        """Get startup stock token metadata and supply info from the blockchain."""
        try:
            return StartupStockContract.to_json(self.contract_client.get_token_info_dict())
        except Exception as e:
            return StartupStockContract.to_json(
                {"error": str(e), "contract_address": self.contract_client.contract_address}
            )

    def get_investor_balance(self, wallet_address: str) -> str:
        """Get an investor's on-chain startup stock balance in shares."""
        try:
            balance_wei = self.contract_client.get_balance_wei(wallet_address)
            return StartupStockContract.to_json(
                {
                    "wallet_address": wallet_address.lower(),
                    "shares": wei_to_shares(balance_wei),
                    "balance_wei": balance_wei,
                }
            )
        except Exception as e:
            return StartupStockContract.to_json({"error": str(e), "wallet_address": wallet_address})

    async def aget_token_info(self) -> str:
        return self.get_token_info()

    async def aget_investor_balance(self, wallet_address: str) -> str:
        return self.get_investor_balance(wallet_address)
