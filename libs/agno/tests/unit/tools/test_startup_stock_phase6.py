"""Unit tests for startup stock phase 6: health, snapshots, sync daemon."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from agno.tools.startup_stock.health import (
    check_cap_table_health,
    check_rpc_health,
    run_health_check,
)
from agno.tools.startup_stock.snapshots import CapTableSnapshotStore
from agno.tools.startup_stock.sync import CapTableEntry, CapTableStore, SyncStatus
from agno.tools.startup_stock.sync_daemon import CapTableSyncDaemon


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestHealth:
    def test_check_rpc_health(self):
        mock_web3 = Mock()
        mock_web3.is_connected.return_value = True
        mock_web3.eth.chain_id = 11155111
        mock_web3.eth.block_number = 1000
        result = check_rpc_health(mock_web3)
        assert result["healthy"] is True
        assert result["chain_id"] == 11155111

    def test_check_cap_table_health_empty(self, temp_dir):
        store = CapTableStore(str(Path(temp_dir) / "cap.db"))
        result = check_cap_table_health(store)
        assert result["status"] == "empty"
        assert result["healthy"] is True

    def test_check_cap_table_health_drift(self, temp_dir):
        store = CapTableStore(str(Path(temp_dir) / "cap.db"))
        store.upsert_entry(
            CapTableEntry(
                investor_name="Alice",
                wallet_address="0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
                shares=1000.0,
                status=SyncStatus.DRIFT,
            )
        )
        result = check_cap_table_health(store)
        assert result["status"] == "critical"
        assert result["healthy"] is False

    def test_run_health_check(self, temp_dir):
        store = CapTableStore(str(Path(temp_dir) / "cap.db"))
        mock_web3 = Mock()
        mock_web3.is_connected.return_value = True
        mock_web3.eth.chain_id = 1
        mock_web3.eth.block_number = 100
        mock_contract = Mock()
        mock_contract.get_token_info_dict.return_value = {
            "name": "Test",
            "symbol": "TST",
            "contract_address": "0xabc",
        }
        result = run_health_check(
            web3_client=mock_web3,
            contract_client=mock_contract,
            cap_table_store=store,
        )
        assert result["healthy"] is True
        assert result["check_count"] >= 3


class TestSnapshots:
    def test_create_and_list(self, temp_dir):
        cap_store = CapTableStore(str(Path(temp_dir) / "cap.db"))
        snap_store = CapTableSnapshotStore(str(Path(temp_dir) / "snap.db"))
        cap_store.upsert_entry(
            CapTableEntry(
                investor_name="Alice",
                wallet_address="0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
                shares=5000.0,
            )
        )
        created = snap_store.create_snapshot(cap_store, "seed-round")
        assert created["investor_count"] == 1
        listed = snap_store.list_snapshots()
        assert len(listed) == 1

    def test_compare_snapshots(self, temp_dir):
        cap_store = CapTableStore(str(Path(temp_dir) / "cap.db"))
        snap_store = CapTableSnapshotStore(str(Path(temp_dir) / "snap.db"))
        cap_store.upsert_entry(
            CapTableEntry(
                investor_name="Alice",
                wallet_address="0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
                shares=5000.0,
            )
        )
        snap_a = snap_store.create_snapshot(cap_store, "before")
        cap_store.upsert_entry(
            CapTableEntry(
                investor_name="Bob",
                wallet_address="0x3Dfc53E3C77bb4e30Ce333Be1a66Ce62558bE395",
                shares=2000.0,
            )
        )
        snap_b = snap_store.create_snapshot(cap_store, "after")
        diff = snap_store.compare_snapshots(snap_a["snapshot_id"], snap_b["snapshot_id"])
        assert len(diff["added"]) == 1
        assert diff["total_shares_delta"] == 2000.0


class TestSyncDaemon:
    def test_run_once(self):
        calls = []

        def sync_fn(dry_run: bool) -> dict:
            calls.append(dry_run)
            return {"synced": 1, "dry_run": dry_run}

        daemon = CapTableSyncDaemon(sync_fn=sync_fn, dry_run=True)
        result = daemon.run_once()
        assert result["synced"] == 1
        assert calls == [True]

    def test_run_max_iterations(self):
        count = {"n": 0}

        def sync_fn(dry_run: bool) -> dict:
            count["n"] += 1
            return {"synced": 0}

        daemon = CapTableSyncDaemon(sync_fn=sync_fn, poll_interval_seconds=0.01)
        daemon.run(max_iterations=2)
        assert count["n"] == 2
