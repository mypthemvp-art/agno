"""Startup stock blockchain toolkit for tokenized equity management."""

from __future__ import annotations

import json
from dataclasses import asdict
from os import getenv
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Callable, Dict, List, Optional

from agno.tools.startup_stock.contracts.abi import STARTUP_STOCK_TOKEN_ABI
from agno.tools.startup_stock.sync import CapTableStore, CapTableSyncEngine, SyncResult
from agno.tools.toolkit import Toolkit
from agno.utils.log import log_debug, log_error

try:
    from eth_account.account import LocalAccount
    from eth_account.datastructures import SignedTransaction
    from hexbytes import HexBytes
    from web3 import Web3
    from web3.contract import Contract
    from web3.main import Web3 as Web3Type
    from web3.providers.rpc import HTTPProvider
    from web3.types import TxParams, TxReceipt
except ImportError:
    raise ImportError("`web3` not installed. Please install using `pip install agno[evm]`")

WEI_PER_SHARE = 10**18


def shares_to_wei(shares: float) -> int:
    return int(shares * WEI_PER_SHARE)


def wei_to_shares(wei: int) -> float:
    return wei / WEI_PER_SHARE


class StartupStockTools(Toolkit):
    """High-security startup equity toolkit with fast cap-table sync.

    Manages ERC-20 startup stock tokens on any EVM chain. Reads on-chain state,
    mints shares to investors, and syncs a local cap table to the blockchain
    with retries and drift detection.
    """

    def __init__(
        self,
        private_key: Optional[str] = None,
        rpc_url: Optional[str] = None,
        contract_address: Optional[str] = None,
        cap_table_db: Optional[str] = None,
        enable_read: bool = True,
        enable_write: bool = True,
        enable_sync: bool = True,
        all: bool = False,
        **kwargs,
    ):
        self.private_key = private_key or getenv("EVM_PRIVATE_KEY")
        self.rpc_url = rpc_url or getenv("EVM_RPC_URL")
        self.contract_address = contract_address or getenv("STARTUP_STOCK_CONTRACT_ADDRESS")

        if not self.private_key:
            raise ValueError("Private key is required (EVM_PRIVATE_KEY or private_key)")
        if not self.rpc_url:
            raise ValueError("RPC URL is required (EVM_RPC_URL or rpc_url)")
        if not self.contract_address:
            raise ValueError("Contract address is required (STARTUP_STOCK_CONTRACT_ADDRESS or contract_address)")

        if not self.private_key.startswith("0x"):
            self.private_key = f"0x{self.private_key}"

        self.web3_client: Web3Type = Web3(HTTPProvider(self.rpc_url))
        self.account: LocalAccount = self.web3_client.eth.account.from_key(self.private_key)
        self.contract: Contract = self.web3_client.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=STARTUP_STOCK_TOKEN_ABI,
        )

        default_db = str(Path(gettempdir()) / "startup_stock_cap_table.db")
        self.cap_table_db: str = cap_table_db or getenv("STARTUP_STOCK_CAP_TABLE_DB") or default_db
        self.store = CapTableStore(self.cap_table_db)
        self.sync_engine = CapTableSyncEngine(
            store=self.store,
            on_chain_reader=self,
            on_chain_minter=self,
            shares_to_wei=shares_to_wei,
            wei_to_shares=wei_to_shares,
        )

        log_debug(f"StartupStockTools wallet: {self.account.address}")
        log_debug(f"StartupStockTools contract: {self.contract_address}")

        tools: List[Callable[..., str]] = []
        async_tools: List[tuple[Callable[..., Any], str]] = []
        if all or enable_read:
            tools.extend(
                [
                    self.get_token_info,
                    self.get_investor_balance,
                    self.list_cap_table,
                ]
            )
            async_tools.extend(
                [
                    (self.aget_token_info, "get_token_info"),
                    (self.aget_investor_balance, "get_investor_balance"),
                    (self.alist_cap_table, "list_cap_table"),
                ]
            )
        if all or enable_write:
            tools.extend(
                [
                    self.add_investor,
                    self.mint_shares,
                    self.transfer_shares,
                ]
            )
            async_tools.extend(
                [
                    (self.aadd_investor, "add_investor"),
                    (self.amint_shares, "mint_shares"),
                    (self.atransfer_shares, "transfer_shares"),
                ]
            )
        if all or enable_sync:
            tools.append(self.sync_cap_table)
            async_tools.append((self.async_cap_table, "sync_cap_table"))

        super().__init__(
            name="startup_stock_tools",
            tools=tools,
            async_tools=async_tools,
            instructions=(
                "Use startup stock tools to manage tokenized startup equity on EVM chains. "
                "Always verify token info and balances before minting or transferring. "
                "Run sync_cap_table with dry_run=True first to preview changes. "
                "Never expose or request private keys in responses."
            ),
            **kwargs,
        )

    # -------------------------------------------------------------------------
    # OnChainReader / OnChainMinter protocol implementations
    # -------------------------------------------------------------------------

    def get_balance(self, wallet_address: str) -> int:
        return int(self.contract.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call())

    def mint_shares_wei(self, wallet_address: str, amount_wei: int) -> str:
        return self._send_contract_tx(
            self.contract.functions.mint(
                Web3.to_checksum_address(wallet_address),
                amount_wei,
            )
        )

    # -------------------------------------------------------------------------
    # Gas helpers
    # -------------------------------------------------------------------------

    def _get_max_priority_fee_per_gas(self) -> int:
        return self.web3_client.to_wei(1, "gwei")

    def _get_max_fee_per_gas(self, max_priority_fee_per_gas: int) -> int:
        latest_block = self.web3_client.eth.get_block("latest")
        base_fee_per_gas = latest_block.get("baseFeePerGas")
        if base_fee_per_gas is None:
            raise ValueError("Base fee per gas not found in the latest block")
        return (2 * base_fee_per_gas) + max_priority_fee_per_gas

    def _send_contract_tx(self, contract_function) -> str:
        try:
            max_priority_fee = self._get_max_priority_fee_per_gas()
            max_fee = self._get_max_fee_per_gas(max_priority_fee)
            nonce = self.web3_client.eth.get_transaction_count(self.account.address)

            tx: TxParams = contract_function.build_transaction(
                {
                    "from": self.account.address,
                    "nonce": nonce,
                    "maxFeePerGas": max_fee,
                    "maxPriorityFeePerGas": max_priority_fee,
                    "chainId": self.web3_client.eth.chain_id,
                    "type": 2,
                }
            )

            if "gas" not in tx or tx["gas"] is None:
                tx["gas"] = self.web3_client.eth.estimate_gas(tx)

            signed: SignedTransaction = self.web3_client.eth.account.sign_transaction(tx, self.private_key)
            tx_hash: HexBytes = self.web3_client.eth.send_raw_transaction(signed.raw_transaction)
            receipt: TxReceipt = self.web3_client.eth.wait_for_transaction_receipt(tx_hash)

            if receipt.get("status") == 1:
                return f"0x{tx_hash.hex()}"
            raise Exception("Transaction failed")
        except Exception as e:
            log_error(f"Contract transaction failed: {e}")
            return f"error: {e}"

    def _json(self, payload: Dict[str, Any]) -> str:
        return json.dumps(payload, default=str)

    # -------------------------------------------------------------------------
    # Read tools
    # -------------------------------------------------------------------------

    def get_token_info(self) -> str:
        """Get startup stock token metadata and supply info from the blockchain."""
        try:
            info = {
                "contract_address": self.contract_address,
                "name": self.contract.functions.name().call(),
                "symbol": self.contract.functions.symbol().call(),
                "decimals": self.contract.functions.decimals().call(),
                "total_supply_shares": wei_to_shares(int(self.contract.functions.totalSupply().call())),
                "max_supply_shares": wei_to_shares(int(self.contract.functions.maxSupply().call())),
                "paused": self.contract.functions.paused().call(),
                "owner": self.contract.functions.owner().call(),
                "wallet": self.account.address,
            }
            return self._json(info)
        except Exception as e:
            return self._json({"error": str(e), "contract_address": self.contract_address})

    def get_investor_balance(self, wallet_address: str) -> str:
        """Get an investor's on-chain startup stock balance in shares."""
        try:
            balance_wei = self.get_balance(wallet_address)
            return self._json(
                {
                    "wallet_address": wallet_address.lower(),
                    "shares": wei_to_shares(balance_wei),
                    "balance_wei": balance_wei,
                }
            )
        except Exception as e:
            return self._json({"error": str(e), "wallet_address": wallet_address})

    def list_cap_table(self) -> str:
        """List the local off-chain cap table with sync status."""
        entries = [asdict(e) for e in self.store.list_entries()]
        for entry in entries:
            if "status" in entry and hasattr(entry["status"], "value"):
                entry["status"] = entry["status"].value
        return self._json({"entries": entries, "count": len(entries), "db_path": self.cap_table_db})

    # -------------------------------------------------------------------------
    # Write tools
    # -------------------------------------------------------------------------

    def add_investor(self, investor_name: str, wallet_address: str, shares: float) -> str:
        """Add or update an investor in the local cap table (off-chain)."""
        try:
            entry = self.sync_engine.add_investor(investor_name, wallet_address, shares)
            payload = asdict(entry)
            payload["status"] = entry.status.value
            return self._json(payload)
        except Exception as e:
            return self._json({"error": str(e), "investor_name": investor_name})

    def mint_shares(self, wallet_address: str, shares: float) -> str:
        """Mint startup stock shares directly on-chain to a wallet address."""
        try:
            amount_wei = shares_to_wei(shares)
            tx_hash = self.mint_shares_wei(wallet_address, amount_wei)
            return self._json(
                {
                    "wallet_address": wallet_address.lower(),
                    "shares": shares,
                    "amount_wei": amount_wei,
                    "tx_hash": tx_hash,
                }
            )
        except Exception as e:
            return self._json({"error": str(e), "wallet_address": wallet_address})

    def transfer_shares(self, to_address: str, shares: float) -> str:
        """Transfer startup stock shares from the connected wallet to another address."""
        try:
            amount_wei = shares_to_wei(shares)
            tx_hash = self._send_contract_tx(
                self.contract.functions.transfer(
                    Web3.to_checksum_address(to_address),
                    amount_wei,
                )
            )
            return self._json(
                {
                    "from": self.account.address,
                    "to": to_address.lower(),
                    "shares": shares,
                    "amount_wei": amount_wei,
                    "tx_hash": tx_hash,
                }
            )
        except Exception as e:
            return self._json({"error": str(e), "to_address": to_address})

    # -------------------------------------------------------------------------
    # Sync tools
    # -------------------------------------------------------------------------

    def sync_cap_table(self, dry_run: bool = True) -> str:
        """Sync the local cap table to the blockchain. Use dry_run=True to preview."""
        try:
            result: SyncResult = self.sync_engine.sync_all(dry_run=dry_run)
            return self._json(asdict(result))
        except Exception as e:
            return self._json({"error": str(e), "dry_run": dry_run})

    # -------------------------------------------------------------------------
    # Async variants
    # -------------------------------------------------------------------------

    async def aget_token_info(self) -> str:
        return self.get_token_info()

    async def aget_investor_balance(self, wallet_address: str) -> str:
        return self.get_investor_balance(wallet_address)

    async def alist_cap_table(self) -> str:
        return self.list_cap_table()

    async def aadd_investor(self, investor_name: str, wallet_address: str, shares: float) -> str:
        return self.add_investor(investor_name, wallet_address, shares)

    async def amint_shares(self, wallet_address: str, shares: float) -> str:
        return self.mint_shares(wallet_address, shares)

    async def atransfer_shares(self, to_address: str, shares: float) -> str:
        return self.transfer_shares(to_address, shares)

    async def async_cap_table(self, dry_run: bool = True) -> str:
        return self.sync_cap_table(dry_run=dry_run)
