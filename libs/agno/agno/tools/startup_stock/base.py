"""Shared Web3 helpers for startup stock tools."""

from __future__ import annotations

import json
from os import getenv
from typing import Any, Dict, Optional

from agno.tools.startup_stock.contracts.abi import STARTUP_STOCK_TOKEN_ABI
from agno.utils.log import log_debug

try:
    from web3 import Web3
    from web3.contract import Contract
    from web3.main import Web3 as Web3Type
    from web3.providers.rpc import HTTPProvider
except ImportError:
    raise ImportError("`web3` not installed. Please install using `pip install agno[evm]`")

WEI_PER_SHARE = 10**18


def shares_to_wei(shares: float) -> int:
    return int(shares * WEI_PER_SHARE)


def wei_to_shares(wei: int) -> float:
    return wei / WEI_PER_SHARE


def resolve_rpc_url(rpc_url: Optional[str] = None) -> str:
    url = rpc_url or getenv("EVM_RPC_URL")
    if not url:
        raise ValueError("RPC URL is required (EVM_RPC_URL or rpc_url)")
    return url


def resolve_contract_address(contract_address: Optional[str] = None) -> str:
    address = contract_address or getenv("STARTUP_STOCK_CONTRACT_ADDRESS")
    if not address:
        raise ValueError("Contract address is required (STARTUP_STOCK_CONTRACT_ADDRESS or contract_address)")
    return address


class StartupStockContract:
    """Read-only connection to a deployed StartupStockToken contract."""

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        contract_address: Optional[str] = None,
    ):
        self.rpc_url = resolve_rpc_url(rpc_url)
        self.contract_address = resolve_contract_address(contract_address)
        self.web3_client: Web3Type = Web3(HTTPProvider(self.rpc_url))
        self.contract: Contract = self.web3_client.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=STARTUP_STOCK_TOKEN_ABI,
        )
        log_debug(f"StartupStockContract: {self.contract_address}")

    def get_balance_wei(self, wallet_address: str) -> int:
        return int(self.contract.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call())

    def get_token_info_dict(self, wallet_address: Optional[str] = None) -> Dict[str, Any]:
        return {
            "contract_address": self.contract_address,
            "name": self.contract.functions.name().call(),
            "symbol": self.contract.functions.symbol().call(),
            "decimals": self.contract.functions.decimals().call(),
            "total_supply_shares": wei_to_shares(int(self.contract.functions.totalSupply().call())),
            "max_supply_shares": wei_to_shares(int(self.contract.functions.maxSupply().call())),
            "paused": self.contract.functions.paused().call(),
            "owner": self.contract.functions.owner().call(),
            "wallet": wallet_address,
        }

    @staticmethod
    def to_json(payload: Dict[str, Any]) -> str:
        return json.dumps(payload, default=str)
