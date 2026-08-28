"""Multi-sig owner management for startup stock contracts."""

from __future__ import annotations

import json
from typing import Any, Dict

from agno.tools.startup_stock.contracts.extended_abi import MULTISIG_ABI

try:
    from web3 import Web3
except ImportError:
    raise ImportError("`web3` not installed. Please install using `pip install agno[evm]`")


class MultiSigManager:
    """Interact with StartupStockMultiSig for privileged operations."""

    def __init__(self, web3_client, multisig_address: str):
        self.web3_client = web3_client
        self.multisig_address = multisig_address
        self.contract = web3_client.eth.contract(
            address=Web3.to_checksum_address(multisig_address),
            abi=MULTISIG_ABI,
        )

    def get_info(self) -> Dict[str, Any]:
        owners = self.contract.functions.getOwners().call()
        required = int(self.contract.functions.required().call())
        tx_count = int(self.contract.functions.transactionCount().call())
        return {
            "multisig_address": self.multisig_address,
            "owners": [o.lower() for o in owners],
            "required_confirmations": required,
            "transaction_count": tx_count,
        }

    def get_transaction(self, tx_id: int) -> Dict[str, Any]:
        txn = self.contract.functions.transactions(tx_id).call()
        confirmations = int(self.contract.functions.getConfirmationCount(tx_id).call())
        return {
            "tx_id": tx_id,
            "target": txn[0].lower(),
            "value": txn[1],
            "data": txn[2].hex() if isinstance(txn[2], bytes) else txn[2],
            "executed": txn[3],
            "confirmations": confirmations,
            "required": int(self.contract.functions.required().call()),
        }

    def submit_transaction(self, target: str, data: bytes, value: int, send_tx_fn) -> str:
        return send_tx_fn(
            self.contract.functions.submitTransaction(
                Web3.to_checksum_address(target),
                value,
                data,
            )
        )

    def confirm_transaction(self, tx_id: int, send_tx_fn) -> str:
        return send_tx_fn(self.contract.functions.confirmTransaction(tx_id))

    def execute_transaction(self, tx_id: int, send_tx_fn) -> str:
        return send_tx_fn(self.contract.functions.executeTransaction(tx_id))

    def is_confirmed(self, tx_id: int, owner_address: str) -> bool:
        return bool(
            self.contract.functions.isConfirmed(
                tx_id,
                Web3.to_checksum_address(owner_address),
            ).call()
        )

    def encode_token_set_minter(self, token_contract, minter: str, allowed: bool) -> bytes:
        fn = token_contract.functions.setMinter(Web3.to_checksum_address(minter), allowed)
        return bytes.fromhex(fn._encode_transaction_data().removeprefix("0x"))

    def encode_token_mint(self, token_contract, to_address: str, amount_wei: int) -> bytes:
        fn = token_contract.functions.mint(Web3.to_checksum_address(to_address), amount_wei)
        return bytes.fromhex(fn._encode_transaction_data().removeprefix("0x"))

    @staticmethod
    def to_json(payload: Any) -> str:
        return json.dumps(payload, default=str)
