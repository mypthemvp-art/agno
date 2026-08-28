"""Unit tests for startup stock phase 3: vesting, multisig, webhooks."""

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from agno.tools.startup_stock.multisig import MultiSigManager
from agno.tools.startup_stock.vesting import (
    VestingSchedule,
    VestingStore,
    compute_releasable_shares,
    compute_vested_shares,
)
from agno.tools.startup_stock.webhooks import (
    TransferEvent,
    TransferWebhookWatcher,
    WebhookDeliveryStore,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestVesting:
    def test_compute_vested_before_cliff(self):
        schedule = VestingSchedule(
            beneficiary="0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
            total_shares=10000.0,
            start_timestamp=1000,
            cliff_seconds=365 * 86400,
            vesting_seconds=4 * 365 * 86400,
        )
        assert compute_vested_shares(schedule, now=1000) == 0.0

    def test_compute_vested_after_cliff(self):
        schedule = VestingSchedule(
            beneficiary="0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
            total_shares=10000.0,
            start_timestamp=0,
            cliff_seconds=0,
            vesting_seconds=1000,
        )
        vested = compute_vested_shares(schedule, now=500)
        assert vested == 5000.0

    def test_compute_releasable(self):
        schedule = VestingSchedule(
            beneficiary="0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
            total_shares=10000.0,
            start_timestamp=0,
            cliff_seconds=0,
            vesting_seconds=1000,
            released_shares=2000.0,
        )
        assert compute_releasable_shares(schedule, now=500) == 3000.0
        assert compute_releasable_shares(schedule, now=1000) == 8000.0

    def test_vesting_store(self, temp_dir):
        store = VestingStore(str(Path(temp_dir) / "vesting.db"))
        schedule = VestingSchedule(
            beneficiary="0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
            total_shares=5000.0,
            start_timestamp=int(time.time()),
            cliff_seconds=86400,
            vesting_seconds=86400 * 365,
        )
        store.upsert(schedule)
        fetched = store.get("0x742d35Cc6634C0532925a3b8D2A7E1234567890A")
        assert fetched is not None
        assert fetched.total_shares == 5000.0


class TestWebhooks:
    def test_event_id_unique(self):
        event = TransferEvent(
            event_type="transfer",
            tx_hash="0xabc",
            block_number=1,
            from_address="0x1111111111111111111111111111111111111111",
            to_address="0x2222222222222222222222222222222222222222",
            value_wei=10**18,
            log_index=0,
        )
        assert len(event.event_id) == 32
        assert event.shares == 1.0

    def test_delivery_store_dedup(self, temp_dir):
        store = WebhookDeliveryStore(str(Path(temp_dir) / "webhooks.db"))
        store.record_delivery("evt1", "0xabc", "http://localhost", "delivered", 200)
        assert store.is_delivered("evt1")
        assert not store.is_delivered("evt2")

    def test_poll_and_deliver(self, temp_dir):
        store = WebhookDeliveryStore(str(Path(temp_dir) / "webhooks.db"))
        mock_contract = Mock()
        mock_event = {
            "args": {
                "from": "0x0000000000000000000000000000000000000000",
                "to": "0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
                "value": 10**18,
            },
            "transactionHash": bytes.fromhex("abcd1234"),
            "blockNumber": 100,
            "logIndex": 0,
        }
        mock_filter = Mock()
        mock_filter.get_all_entries.return_value = [mock_event]
        mock_contract.events.Transfer.create_filter.return_value = mock_filter

        mock_web3 = Mock()
        mock_web3.eth.block_number = 100

        delivered_payloads = []

        def mock_post(url, payload):
            delivered_payloads.append(payload)
            return 200, "ok"

        watcher = TransferWebhookWatcher(
            contract=mock_contract,
            web3_client=mock_web3,
            webhook_url="http://localhost/hook",
            store=store,
            http_post_fn=mock_post,
        )
        result = watcher.poll_and_deliver(lookback_blocks=10)
        assert result["delivered"] == 1
        assert len(delivered_payloads) == 1
        assert delivered_payloads[0]["event_type"] == "mint"


class TestMultiSig:
    def test_get_info(self):
        mock_web3 = Mock()
        mock_contract = Mock()
        mock_contract.functions.getOwners.return_value.call.return_value = [
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222",
        ]
        mock_contract.functions.required.return_value.call.return_value = 2
        mock_contract.functions.transactionCount.return_value.call.return_value = 5
        mock_web3.eth.contract.return_value = mock_contract

        with patch("agno.tools.startup_stock.multisig.Web3") as mock_web3_mod:
            mock_web3_mod.to_checksum_address = lambda x: x
            manager = MultiSigManager(mock_web3, "0x3333333333333333333333333333333333333333")
            manager.contract = mock_contract
            info = manager.get_info()
            assert info["required_confirmations"] == 2
            assert len(info["owners"]) == 2
