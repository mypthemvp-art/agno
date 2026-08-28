"""Advanced startup stock tools: vesting, multi-sig, and transfer webhooks."""

from __future__ import annotations

import time
from os import getenv
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Callable, List, Optional

from agno.tools.startup_stock.multisig import MultiSigManager
from agno.tools.startup_stock.toolkit import StartupStockTools, _to_json
from agno.tools.startup_stock.vesting import (
    VestingManager,
    VestingSchedule,
    VestingStore,
    compute_releasable_shares,
    compute_vested_shares,
)
from agno.tools.startup_stock.webhooks import TransferWebhookWatcher, WebhookDeliveryStore


class StartupStockAdvancedTools(StartupStockTools):
    """Extended toolkit with vesting schedules, multi-sig owner, and transfer webhooks."""

    def __init__(
        self,
        vesting_vault_address: Optional[str] = None,
        multisig_address: Optional[str] = None,
        webhook_url: Optional[str] = None,
        enable_vesting: bool = True,
        enable_multisig: bool = True,
        enable_webhooks: bool = True,
        all_advanced: bool = False,
        **kwargs,
    ):
        self._enable_vesting = all_advanced or enable_vesting
        self._enable_multisig = all_advanced or enable_multisig
        self._enable_webhooks = all_advanced or enable_webhooks

        super().__init__(**kwargs)

        self.vesting_vault_address = vesting_vault_address or getenv("STARTUP_STOCK_VESTING_VAULT")
        self.multisig_address = multisig_address or getenv("STARTUP_STOCK_MULTISIG_ADDRESS")
        self.webhook_url = webhook_url or getenv("STARTUP_STOCK_WEBHOOK_URL")

        vesting_db = str(Path(gettempdir()) / "startup_stock_vesting.db")
        webhook_db = str(Path(gettempdir()) / "startup_stock_webhooks.db")
        self.vesting_store = VestingStore(vesting_db)
        self.webhook_store = WebhookDeliveryStore(webhook_db)

        assert self.private_key is not None
        self.vesting_manager = VestingManager(
            self.web3_client,
            self.account,
            self.private_key,
            self.vesting_vault_address,
        )
        self.multisig_manager = (
            MultiSigManager(self.web3_client, self.multisig_address) if self.multisig_address else None
        )

        extra_tools: List[Callable[..., str]] = []
        extra_async: List[tuple[Callable[..., Any], str]] = []

        if self._enable_vesting:
            extra_tools.extend(
                [
                    self.create_vesting_schedule,
                    self.get_vesting_schedule,
                    self.list_vesting_schedules,
                    self.release_vested_shares,
                ]
            )
            extra_async.extend(
                [
                    (self.acreate_vesting_schedule, "create_vesting_schedule"),
                    (self.aget_vesting_schedule, "get_vesting_schedule"),
                    (self.alist_vesting_schedules, "list_vesting_schedules"),
                    (self.arelease_vested_shares, "release_vested_shares"),
                ]
            )

        if self._enable_multisig:
            extra_tools.extend(
                [
                    self.get_multisig_info,
                    self.submit_multisig_transaction,
                    self.confirm_multisig_transaction,
                    self.get_multisig_transaction,
                ]
            )
            extra_async.extend(
                [
                    (self.aget_multisig_info, "get_multisig_info"),
                    (self.asubmit_multisig_transaction, "submit_multisig_transaction"),
                    (self.aconfirm_multisig_transaction, "confirm_multisig_transaction"),
                    (self.aget_multisig_transaction, "get_multisig_transaction"),
                ]
            )

        if self._enable_webhooks:
            extra_tools.append(self.poll_transfer_webhooks)
            extra_async.append((self.apoll_transfer_webhooks, "poll_transfer_webhooks"))

        for tool in extra_tools:
            self.register(tool)
        for async_fn, tool_name in extra_async:
            self.register(async_fn, name=tool_name)

    # -------------------------------------------------------------------------
    # Vesting tools
    # -------------------------------------------------------------------------

    def create_vesting_schedule(
        self,
        beneficiary: str,
        total_shares: float,
        cliff_days: int = 365,
        vesting_days: int = 1460,
        start_timestamp: Optional[int] = None,
    ) -> str:
        """Create a linear vesting schedule with cliff for an investor."""
        try:
            start = start_timestamp or int(time.time())
            cliff_seconds = cliff_days * 86400
            vesting_seconds = vesting_days * 86400

            schedule = VestingSchedule(
                beneficiary=beneficiary.lower(),
                total_shares=total_shares,
                start_timestamp=start,
                cliff_seconds=cliff_seconds,
                vesting_seconds=vesting_seconds,
                vault_address=self.vesting_vault_address,
            )
            self.vesting_store.upsert(schedule)

            tx_hash = None
            if self.vesting_vault_address:
                tx_hash = self.vesting_manager.create_schedule_on_chain(
                    beneficiary,
                    total_shares,
                    start,
                    cliff_seconds,
                    vesting_seconds,
                    self._send_contract_tx,
                )

            return _to_json({**schedule.to_dict(), "tx_hash": tx_hash})
        except Exception as e:
            return _to_json({"error": str(e), "beneficiary": beneficiary})

    def get_vesting_schedule(self, beneficiary: str) -> str:
        """Get vesting schedule for a beneficiary (local + on-chain if vault configured)."""
        try:
            local = self.vesting_store.get(beneficiary)
            if not local and not self.vesting_vault_address:
                return _to_json({"error": "Schedule not found", "beneficiary": beneficiary})

            payload: dict = {}
            if local:
                payload = local.to_dict()
                payload["vested_shares"] = compute_vested_shares(local)
                payload["releasable_shares"] = compute_releasable_shares(local)

            if self.vesting_vault_address:
                payload["on_chain"] = self.vesting_manager.get_schedule_on_chain(beneficiary)

            return _to_json(payload)
        except Exception as e:
            return _to_json({"error": str(e), "beneficiary": beneficiary})

    def list_vesting_schedules(self) -> str:
        """List all local vesting schedules with vested/releasable amounts."""
        try:
            schedules = []
            for s in self.vesting_store.list_schedules():
                item = s.to_dict()
                item["vested_shares"] = compute_vested_shares(s)
                item["releasable_shares"] = compute_releasable_shares(s)
                schedules.append(item)
            return _to_json({"schedules": schedules, "count": len(schedules)})
        except Exception as e:
            return _to_json({"error": str(e)})

    def release_vested_shares(self, beneficiary: str) -> str:
        """Release vested shares from the vesting vault to the beneficiary."""
        try:
            tx_hash = None
            if self.vesting_vault_address:
                tx_hash = self.vesting_manager.release_on_chain(beneficiary, self._send_contract_tx)

            local = self.vesting_store.get(beneficiary)
            releasable = compute_releasable_shares(local) if local else 0.0
            if local and releasable > 0:
                local.released_shares += releasable
                self.vesting_store.upsert(local)

            return _to_json(
                {
                    "beneficiary": beneficiary.lower(),
                    "released_shares": releasable,
                    "tx_hash": tx_hash,
                }
            )
        except Exception as e:
            return _to_json({"error": str(e), "beneficiary": beneficiary})

    # -------------------------------------------------------------------------
    # Multi-sig tools
    # -------------------------------------------------------------------------

    def _require_multisig(self) -> MultiSigManager:
        if not self.multisig_manager:
            raise ValueError("Multi-sig address not configured (STARTUP_STOCK_MULTISIG_ADDRESS)")
        return self.multisig_manager

    def get_multisig_info(self) -> str:
        """Get multi-sig wallet configuration and transaction count."""
        try:
            return _to_json(self._require_multisig().get_info())
        except Exception as e:
            return _to_json({"error": str(e)})

    def submit_multisig_transaction(self, target: str, data_hex: str, value_wei: int = 0) -> str:
        """Submit a transaction to the multi-sig for owner confirmation."""
        try:
            data = bytes.fromhex(data_hex.removeprefix("0x"))
            tx_hash = self._require_multisig().submit_transaction(target, data, value_wei, self._send_contract_tx)
            return _to_json({"target": target.lower(), "tx_hash": tx_hash})
        except Exception as e:
            return _to_json({"error": str(e), "target": target})

    def confirm_multisig_transaction(self, tx_id: int) -> str:
        """Confirm a pending multi-sig transaction."""
        try:
            tx_hash = self._require_multisig().confirm_transaction(tx_id, self._send_contract_tx)
            return _to_json({"tx_id": tx_id, "tx_hash": tx_hash})
        except Exception as e:
            return _to_json({"error": str(e), "tx_id": tx_id})

    def get_multisig_transaction(self, tx_id: int) -> str:
        """Get details and confirmation status of a multi-sig transaction."""
        try:
            return _to_json(self._require_multisig().get_transaction(tx_id))
        except Exception as e:
            return _to_json({"error": str(e), "tx_id": tx_id})

    # -------------------------------------------------------------------------
    # Webhook tools
    # -------------------------------------------------------------------------

    def poll_transfer_webhooks(self, lookback_blocks: int = 100) -> str:
        """Poll Transfer events and deliver to configured webhook URL."""
        try:
            if not self.webhook_url:
                return _to_json({"error": "Webhook URL not configured (STARTUP_STOCK_WEBHOOK_URL)"})
            contract = self._require_contract().contract
            watcher = TransferWebhookWatcher(
                contract=contract,
                web3_client=self.web3_client,
                webhook_url=self.webhook_url,
                store=self.webhook_store,
            )
            return _to_json(watcher.poll_and_deliver(lookback_blocks=lookback_blocks))
        except Exception as e:
            return _to_json({"error": str(e)})

    # -------------------------------------------------------------------------
    # Async variants
    # -------------------------------------------------------------------------

    async def acreate_vesting_schedule(
        self,
        beneficiary: str,
        total_shares: float,
        cliff_days: int = 365,
        vesting_days: int = 1460,
        start_timestamp: Optional[int] = None,
    ) -> str:
        return self.create_vesting_schedule(beneficiary, total_shares, cliff_days, vesting_days, start_timestamp)

    async def aget_vesting_schedule(self, beneficiary: str) -> str:
        return self.get_vesting_schedule(beneficiary)

    async def alist_vesting_schedules(self) -> str:
        return self.list_vesting_schedules()

    async def arelease_vested_shares(self, beneficiary: str) -> str:
        return self.release_vested_shares(beneficiary)

    async def aget_multisig_info(self) -> str:
        return self.get_multisig_info()

    async def asubmit_multisig_transaction(self, target: str, data_hex: str, value_wei: int = 0) -> str:
        return self.submit_multisig_transaction(target, data_hex, value_wei)

    async def aconfirm_multisig_transaction(self, tx_id: int) -> str:
        return self.confirm_multisig_transaction(tx_id)

    async def aget_multisig_transaction(self, tx_id: int) -> str:
        return self.get_multisig_transaction(tx_id)

    async def apoll_transfer_webhooks(self, lookback_blocks: int = 100) -> str:
        return self.poll_transfer_webhooks(lookback_blocks=lookback_blocks)
