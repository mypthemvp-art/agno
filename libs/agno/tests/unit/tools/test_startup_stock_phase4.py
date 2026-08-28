"""Unit tests for startup stock phase 4: reports, deploy extensions, webhook daemon."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from agno.tools.startup_stock.deploy import deploy_multisig, deploy_vesting_vault
from agno.tools.startup_stock.reports import (
    DilutionScenario,
    calculate_dilution,
    export_compliance_report,
    generate_equity_report,
)
from agno.tools.startup_stock.sync import CapTableEntry, CapTableStore, SyncStatus
from agno.tools.startup_stock.webhook_daemon import TransferWebhookDaemon


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestReports:
    def test_calculate_dilution(self):
        shareholders = [
            {"investor_name": "Alice", "wallet_address": "0xaaa", "shares": 60000},
            {"investor_name": "Bob", "wallet_address": "0xbbb", "shares": 40000},
        ]
        scenarios = [DilutionScenario(name="Series A", new_shares=20000, option_pool_increase=5000)]
        result = calculate_dilution(shareholders, scenarios)

        assert result["total_shares"] == 100000
        assert len(result["scenarios"]) == 1
        alice = result["scenarios"][0]["shareholders"][0]
        assert alice["investor_name"] == "Alice"
        assert alice["ownership_pct"] < 60.0

    def test_calculate_dilution_empty(self):
        result = calculate_dilution([], [DilutionScenario(name="Empty", new_shares=1000)])
        assert "error" in result

    def test_generate_equity_report(self, temp_dir):
        store = CapTableStore(str(Path(temp_dir) / "cap.db"))
        store.upsert_entry(
            CapTableEntry(
                investor_name="Alice",
                wallet_address="0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
                shares=1000.0,
                status=SyncStatus.PENDING,
            )
        )

        mock_reader = Mock()
        mock_reader.get_balance.return_value = int(1000.0 * 10**18)

        report = generate_equity_report(
            cap_table_store=store,
            on_chain_reader=mock_reader,
            shares_to_wei=lambda s: int(s * 10**18),
            wei_to_shares=lambda w: w / 10**18,
        )
        assert report["summary"]["investor_count"] == 1
        assert report["investors"][0]["on_chain_verified"] is True

    def test_export_compliance_report_json(self, temp_dir):
        report = {
            "summary": {"investor_count": 1},
            "investors": [
                {
                    "investor_name": "Alice",
                    "wallet_address": "0xaaa",
                    "shares": 1000,
                    "ownership_pct": 100,
                    "status": "pending",
                }
            ],
        }
        out_path = str(Path(temp_dir) / "report.json")
        result = export_compliance_report(report, out_path, fmt="json")
        assert result["format"] == "json"
        assert Path(out_path).exists()

    def test_export_compliance_report_csv(self, temp_dir):
        report = {
            "summary": {"investor_count": 1},
            "investors": [
                {
                    "investor_name": "Alice",
                    "wallet_address": "0xaaa",
                    "shares": 1000,
                    "ownership_pct": 100,
                    "status": "pending",
                }
            ],
        }
        out_path = str(Path(temp_dir) / "report.csv")
        result = export_compliance_report(report, out_path, fmt="csv")
        assert result["format"] == "csv"
        assert Path(out_path).exists()


class TestDeployExtensions:
    def test_deploy_vesting_vault_no_forge(self):
        with patch("agno.tools.startup_stock.deploy.shutil.which", return_value=None):
            result = deploy_vesting_vault(
                token_address="0x1111111111111111111111111111111111111111",
                rpc_url="http://localhost:8545",
                private_key="0x" + "11" * 32,
            )
            assert "error" in result

    def test_deploy_multisig_invalid_required(self):
        result = deploy_multisig(
            owners=["0x1111111111111111111111111111111111111111"],
            required=2,
            rpc_url="http://localhost:8545",
            private_key="0x" + "11" * 32,
        )
        assert "error" in result


class TestWebhookDaemon:
    def test_run_once(self):
        mock_watcher = Mock()
        mock_watcher.poll_and_deliver.return_value = {
            "events_found": 1,
            "delivered": 1,
            "failed": 0,
        }
        daemon = TransferWebhookDaemon(mock_watcher, lookback_blocks=10)
        result = daemon.run_once()
        assert result["delivered"] == 1
        mock_watcher.poll_and_deliver.assert_called_once_with(lookback_blocks=10)

    def test_run_max_iterations(self):
        mock_watcher = Mock()
        mock_watcher.poll_and_deliver.return_value = {"events_found": 0, "delivered": 0, "failed": 0}
        daemon = TransferWebhookDaemon(mock_watcher, poll_interval_seconds=0.01)
        daemon.run(max_iterations=2)
        assert mock_watcher.poll_and_deliver.call_count == 2
