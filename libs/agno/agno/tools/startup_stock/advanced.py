"""Advanced startup stock tools: vesting, multi-sig, and transfer webhooks."""

from __future__ import annotations

import json
import time
from os import getenv
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Callable, List, Optional

from agno.tools.startup_stock.audit import AuditStore
from agno.tools.startup_stock.deploy import deploy_multisig, deploy_vesting_vault
from agno.tools.startup_stock.health import run_health_check
from agno.tools.startup_stock.multisig import MultiSigManager
from agno.tools.startup_stock.reports import (
    DilutionScenario,
)
from agno.tools.startup_stock.reports import (
    calculate_dilution as calc_dilution,
)
from agno.tools.startup_stock.reports import (
    export_compliance_report as export_report,
)
from agno.tools.startup_stock.reports import (
    generate_equity_report as build_equity_report,
)
from agno.tools.startup_stock.snapshots import CapTableSnapshotStore
from agno.tools.startup_stock.sync_daemon import CapTableSyncDaemon
from agno.tools.startup_stock.toolkit import StartupStockTools, _to_json, shares_to_wei, wei_to_shares
from agno.tools.startup_stock.vesting import (
    VestingManager,
    VestingSchedule,
    VestingStore,
    compute_releasable_shares,
    compute_vested_shares,
)
from agno.tools.startup_stock.webhook_daemon import TransferWebhookDaemon
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
        enable_reports: bool = True,
        enable_deploy_extended: bool = True,
        enable_audit: bool = True,
        enable_health: bool = True,
        enable_snapshots: bool = True,
        all_advanced: bool = False,
        **kwargs,
    ):
        self._enable_vesting = all_advanced or enable_vesting
        self._enable_multisig = all_advanced or enable_multisig
        self._enable_webhooks = all_advanced or enable_webhooks
        self._enable_reports = all_advanced or enable_reports
        self._enable_deploy_extended = all_advanced or enable_deploy_extended
        self._enable_audit = all_advanced or enable_audit
        self._enable_health = all_advanced or enable_health
        self._enable_snapshots = all_advanced or enable_snapshots

        super().__init__(**kwargs)

        self.vesting_vault_address = vesting_vault_address or getenv("STARTUP_STOCK_VESTING_VAULT")
        self.multisig_address = multisig_address or getenv("STARTUP_STOCK_MULTISIG_ADDRESS")
        self.webhook_url = webhook_url or getenv("STARTUP_STOCK_WEBHOOK_URL")

        vesting_db = str(Path(gettempdir()) / "startup_stock_vesting.db")
        webhook_db = str(Path(gettempdir()) / "startup_stock_webhooks.db")
        audit_db = str(Path(gettempdir()) / "startup_stock_audit.db")
        snapshot_db = str(Path(gettempdir()) / "startup_stock_snapshots.db")
        self.vesting_store = VestingStore(vesting_db)
        self.webhook_store = WebhookDeliveryStore(webhook_db)
        self.audit_store = AuditStore(audit_db)
        self.snapshot_store = CapTableSnapshotStore(snapshot_db)

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
            extra_tools.extend(
                [
                    self.poll_transfer_webhooks,
                    self.run_webhook_daemon_once,
                ]
            )
            extra_async.extend(
                [
                    (self.apoll_transfer_webhooks, "poll_transfer_webhooks"),
                    (self.arun_webhook_daemon_once, "run_webhook_daemon_once"),
                ]
            )

        if self._enable_reports:
            extra_tools.extend(
                [
                    self.generate_equity_report,
                    self.calculate_dilution,
                    self.export_compliance_report,
                ]
            )
            extra_async.extend(
                [
                    (self.agenerate_equity_report, "generate_equity_report"),
                    (self.acalculate_dilution, "calculate_dilution"),
                    (self.aexport_compliance_report, "export_compliance_report"),
                ]
            )

        if self._enable_deploy_extended:
            extra_tools.extend(
                [
                    self.deploy_vesting_vault,
                    self.deploy_multisig,
                ]
            )
            extra_async.extend(
                [
                    (self.adeploy_vesting_vault, "deploy_vesting_vault"),
                    (self.adeploy_multisig, "deploy_multisig"),
                ]
            )

        if self._enable_audit:
            extra_tools.extend([self.get_audit_log, self.log_audit_event])
            extra_async.extend(
                [
                    (self.aget_audit_log, "get_audit_log"),
                    (self.alog_audit_event, "log_audit_event"),
                ]
            )

        if self._enable_health:
            extra_tools.extend([self.run_health_check, self.run_sync_daemon_once])
            extra_async.extend(
                [
                    (self.arun_health_check, "run_health_check"),
                    (self.arun_sync_daemon_once, "run_sync_daemon_once"),
                ]
            )

        if self._enable_snapshots:
            extra_tools.extend(
                [
                    self.create_cap_table_snapshot,
                    self.list_cap_table_snapshots,
                    self.compare_cap_table_snapshots,
                ]
            )
            extra_async.extend(
                [
                    (self.acreate_cap_table_snapshot, "create_cap_table_snapshot"),
                    (self.alist_cap_table_snapshots, "list_cap_table_snapshots"),
                    (self.acompare_cap_table_snapshots, "compare_cap_table_snapshots"),
                ]
            )

        for tool in extra_tools:
            self.register(tool)
        for async_fn, tool_name in extra_async:
            self.register(async_fn, name=tool_name)

    def _log_audit(
        self,
        action: str,
        target: Optional[str] = None,
        detail: Optional[Any] = None,
    ) -> None:
        if self._enable_audit:
            self.audit_store.record(action=action, actor=self.account.address, target=target, detail=detail)

    # -------------------------------------------------------------------------
    # Cap table overrides (with audit trail)
    # -------------------------------------------------------------------------

    def add_investor(self, investor_name: str, wallet_address: str, shares: float) -> str:
        result = super().add_investor(investor_name, wallet_address, shares)
        self._log_audit(
            "add_investor",
            target=wallet_address.lower(),
            detail={"investor_name": investor_name, "shares": shares},
        )
        return result

    def sync_cap_table(self, dry_run: bool = True) -> str:
        result = super().sync_cap_table(dry_run=dry_run)
        self._log_audit("sync_cap_table", detail={"dry_run": dry_run})
        return result

    # -------------------------------------------------------------------------
    # Audit tools
    # -------------------------------------------------------------------------

    def get_audit_log(self, limit: int = 50, action: Optional[str] = None) -> str:
        """Get recent audit log entries for compliance review."""
        try:
            events = [e.to_dict() for e in self.audit_store.list_events(limit=limit, action=action)]
            return _to_json({"events": events, "count": len(events)})
        except Exception as e:
            return _to_json({"error": str(e)})

    def log_audit_event(self, action: str, target: Optional[str] = None, detail: Optional[str] = None) -> str:
        """Manually record an audit event (e.g. board approval, 409A valuation)."""
        try:
            event = self.audit_store.record(
                action=action,
                actor=self.account.address,
                target=target,
                detail=detail,
            )
            return _to_json(event.to_dict())
        except Exception as e:
            return _to_json({"error": str(e), "action": action})

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

            self._log_audit(
                "create_vesting_schedule",
                target=beneficiary.lower(),
                detail={"total_shares": total_shares, "tx_hash": tx_hash},
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

            self._log_audit(
                "release_vested_shares",
                target=beneficiary.lower(),
                detail={"released_shares": releasable, "tx_hash": tx_hash},
            )
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
            self._log_audit("submit_multisig_transaction", target=target.lower(), detail={"tx_hash": tx_hash})
            return _to_json({"target": target.lower(), "tx_hash": tx_hash})
        except Exception as e:
            return _to_json({"error": str(e), "target": target})

    def confirm_multisig_transaction(self, tx_id: int) -> str:
        """Confirm a pending multi-sig transaction."""
        try:
            tx_hash = self._require_multisig().confirm_transaction(tx_id, self._send_contract_tx)
            self._log_audit("confirm_multisig_transaction", detail={"tx_id": tx_id, "tx_hash": tx_hash})
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
            watcher = self._build_webhook_watcher()
            return _to_json(watcher.poll_and_deliver(lookback_blocks=lookback_blocks))
        except Exception as e:
            return _to_json({"error": str(e)})

    def run_webhook_daemon_once(self, lookback_blocks: int = 50) -> str:
        """Run a single webhook daemon poll cycle."""
        try:
            if not self.webhook_url:
                return _to_json({"error": "Webhook URL not configured (STARTUP_STOCK_WEBHOOK_URL)"})
            daemon = TransferWebhookDaemon(
                watcher=self._build_webhook_watcher(),
                lookback_blocks=lookback_blocks,
            )
            return _to_json(daemon.run_once())
        except Exception as e:
            return _to_json({"error": str(e)})

    def _build_webhook_watcher(self) -> TransferWebhookWatcher:
        if not self.webhook_url:
            raise ValueError("Webhook URL not configured (STARTUP_STOCK_WEBHOOK_URL)")
        contract = self._require_contract().contract
        return TransferWebhookWatcher(
            contract=contract,
            web3_client=self.web3_client,
            webhook_url=self.webhook_url,
            store=self.webhook_store,
        )

    # -------------------------------------------------------------------------
    # Report tools
    # -------------------------------------------------------------------------

    def generate_equity_report(self) -> str:
        """Generate a comprehensive equity report with on-chain verification."""
        try:
            on_chain_reader = self if self.contract_client else None
            report = build_equity_report(
                cap_table_store=self.store,
                vesting_store=self.vesting_store if self._enable_vesting else None,
                on_chain_reader=on_chain_reader,
                shares_to_wei=shares_to_wei,
                wei_to_shares=wei_to_shares,
            )
            return _to_json(report)
        except Exception as e:
            return _to_json({"error": str(e)})

    def calculate_dilution(
        self,
        scenario_name: str,
        new_shares: float,
        option_pool_increase: float = 0.0,
    ) -> str:
        """Calculate ownership dilution for a funding scenario."""
        try:
            entries = self.store.list_entries()
            shareholders = [
                {
                    "investor_name": e.investor_name,
                    "wallet_address": e.wallet_address,
                    "shares": e.shares,
                }
                for e in entries
            ]
            scenarios = [
                DilutionScenario(
                    name=scenario_name,
                    new_shares=new_shares,
                    option_pool_increase=option_pool_increase,
                )
            ]
            return _to_json(calc_dilution(shareholders, scenarios))
        except Exception as e:
            return _to_json({"error": str(e), "scenario_name": scenario_name})

    def export_compliance_report(self, file_path: str, fmt: str = "json") -> str:
        """Export equity report to JSON or CSV for compliance/audit."""
        try:
            report = build_equity_report(
                cap_table_store=self.store,
                vesting_store=self.vesting_store if self._enable_vesting else None,
                on_chain_reader=self if self.contract_client else None,
                shares_to_wei=shares_to_wei,
                wei_to_shares=wei_to_shares,
            )
            result = export_report(report, file_path, fmt=fmt)
            self._log_audit("export_compliance_report", detail={"file_path": file_path, "format": fmt})
            return _to_json(result)
        except Exception as e:
            return _to_json({"error": str(e), "file_path": file_path})

    # -------------------------------------------------------------------------
    # Extended deploy tools
    # -------------------------------------------------------------------------

    def deploy_vesting_vault(self, token_address: Optional[str] = None) -> str:
        """Deploy VestingVault for the startup stock token."""
        try:
            token = token_address or self.contract_address
            if not token:
                return _to_json({"error": "Token address required (contract_address or token_address)"})
            assert self.rpc_url is not None and self.private_key is not None
            result = deploy_vesting_vault(
                token_address=token,
                rpc_url=self.rpc_url,
                private_key=self.private_key,
            )
            if "contract_address" in result:
                self.vesting_vault_address = result["contract_address"]
                self.vesting_manager.set_vault_address(result["contract_address"])
            return _to_json(result)
        except Exception as e:
            return _to_json({"error": str(e)})

    def deploy_multisig(self, owners_csv: str, required: int) -> str:
        """Deploy StartupStockMultiSig. owners_csv is comma-separated addresses."""
        try:
            owners = [o.strip() for o in owners_csv.split(",") if o.strip()]
            assert self.rpc_url is not None and self.private_key is not None
            result = deploy_multisig(
                owners=owners,
                required=required,
                rpc_url=self.rpc_url,
                private_key=self.private_key,
            )
            if "contract_address" in result:
                self.multisig_address = result["contract_address"]
                self.multisig_manager = MultiSigManager(self.web3_client, self.multisig_address)
            return _to_json(result)
        except Exception as e:
            return _to_json({"error": str(e)})

    # -------------------------------------------------------------------------
    # Health and sync daemon tools
    # -------------------------------------------------------------------------

    def run_health_check(self) -> str:
        """Run infrastructure health checks (RPC, contract, cap table, config)."""
        try:
            result = run_health_check(
                web3_client=self.web3_client,
                contract_client=self.contract_client,
                cap_table_store=self.store,
                vesting_vault_configured=bool(self.vesting_vault_address),
                multisig_configured=bool(self.multisig_address),
                webhook_configured=bool(self.webhook_url),
            )
            return _to_json(result)
        except Exception as e:
            return _to_json({"error": str(e)})

    def run_sync_daemon_once(self, dry_run: bool = True) -> str:
        """Run a single cap table sync daemon cycle."""
        try:

            def sync_fn(dry: bool) -> dict:
                return json.loads(self.sync_cap_table(dry_run=dry))

            daemon = CapTableSyncDaemon(sync_fn=sync_fn, dry_run=dry_run)
            return _to_json(daemon.run_once())
        except Exception as e:
            return _to_json({"error": str(e)})

    # -------------------------------------------------------------------------
    # Snapshot tools
    # -------------------------------------------------------------------------

    def create_cap_table_snapshot(self, label: str) -> str:
        """Create a point-in-time cap table snapshot for compliance."""
        try:
            result = self.snapshot_store.create_snapshot(self.store, label)
            self._log_audit("create_snapshot", detail=result)
            return _to_json(result)
        except Exception as e:
            return _to_json({"error": str(e), "label": label})

    def list_cap_table_snapshots(self, limit: int = 20) -> str:
        """List cap table snapshots ordered by creation time."""
        try:
            snapshots = self.snapshot_store.list_snapshots(limit=limit)
            return _to_json({"snapshots": snapshots, "count": len(snapshots)})
        except Exception as e:
            return _to_json({"error": str(e)})

    def compare_cap_table_snapshots(self, snapshot_id_a: str, snapshot_id_b: str) -> str:
        """Compare two cap table snapshots and show diffs."""
        try:
            return _to_json(self.snapshot_store.compare_snapshots(snapshot_id_a, snapshot_id_b))
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

    async def arun_webhook_daemon_once(self, lookback_blocks: int = 50) -> str:
        return self.run_webhook_daemon_once(lookback_blocks=lookback_blocks)

    async def agenerate_equity_report(self) -> str:
        return self.generate_equity_report()

    async def acalculate_dilution(
        self,
        scenario_name: str,
        new_shares: float,
        option_pool_increase: float = 0.0,
    ) -> str:
        return self.calculate_dilution(scenario_name, new_shares, option_pool_increase)

    async def aexport_compliance_report(self, file_path: str, fmt: str = "json") -> str:
        return self.export_compliance_report(file_path, fmt=fmt)

    async def adeploy_vesting_vault(self, token_address: Optional[str] = None) -> str:
        return self.deploy_vesting_vault(token_address=token_address)

    async def adeploy_multisig(self, owners_csv: str, required: int) -> str:
        return self.deploy_multisig(owners_csv, required)

    async def aget_audit_log(self, limit: int = 50, action: Optional[str] = None) -> str:
        return self.get_audit_log(limit=limit, action=action)

    async def alog_audit_event(self, action: str, target: Optional[str] = None, detail: Optional[str] = None) -> str:
        return self.log_audit_event(action, target=target, detail=detail)

    async def arun_health_check(self) -> str:
        return self.run_health_check()

    async def arun_sync_daemon_once(self, dry_run: bool = True) -> str:
        return self.run_sync_daemon_once(dry_run=dry_run)

    async def acreate_cap_table_snapshot(self, label: str) -> str:
        return self.create_cap_table_snapshot(label)

    async def alist_cap_table_snapshots(self, limit: int = 20) -> str:
        return self.list_cap_table_snapshots(limit=limit)

    async def acompare_cap_table_snapshots(self, snapshot_id_a: str, snapshot_id_b: str) -> str:
        return self.compare_cap_table_snapshots(snapshot_id_a, snapshot_id_b)
